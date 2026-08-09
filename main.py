import asyncio

from aiohttp import ClientSession

from src.cli import build_parser, query_from_args
from src.config import settings
from src.logger import get_logger
from src.schemas.job import JobQuery
from src.services.ai import OllamaAIService
from src.services.deterministic_filter import DEFAULT_PREFERENCES
from src.services.email import GmailService
from src.services.listing import get_listing_service
from src.services.query_filter import apply_client_filters
from src.services.state import JobStateStore, config_key, offer_key, utc_now

DEFAULT_EMAIL_TO = settings.get_env("EMAIL_TO")
DEFAULT_STATE_DB = settings.get("state", "db_path", default="state/jobs.db")
logger = get_logger(__name__)


def format_jobs(jobs: dict) -> str:
    lines = []
    for job in jobs.values():
        lines.append(job.title)
        lines.append(job.url)
        lines.append("")
    return "\n".join(lines).strip()


async def collect_jobs(session, providers: list[str], query: JobQuery) -> dict:
    jobs = {}
    seen_urls = set()
    active_fields = query.active_fields()
    for name in providers:
        logger.info("Searching provider '%s'", name)
        service = get_listing_service(name, session)
        unsupported = active_fields - service.SUPPORTED_QUERY_FIELDS
        fetched = await service.search(query)
        filtered = apply_client_filters(fetched, query, unsupported, provider=name)
        logger.debug(
            "Provider '%s': %d fetched, %d after client-side filters",
            name,
            len(fetched),
            len(filtered),
        )
        for slug, job in filtered.items():
            if job.url and job.url in seen_urls:
                continue
            if job.url:
                seen_urls.add(job.url)
            jobs[f"{name}/{slug}"] = job
    return jobs


async def main(argv=None):
    args = build_parser().parse_args(argv)
    query = query_from_args(args)
    run_key = config_key(args.provider, query, args.preferences)
    logger.info(
        "Run started; providers=%s query=%s config=%s",
        args.provider,
        query.model_dump(),
        run_key,
    )

    try:
        async with ClientSession() as session:
            jobs = await collect_jobs(session, args.provider, query)
        logger.info("Collected %d jobs", len(jobs))

        with JobStateStore(DEFAULT_STATE_DB) as store:
            analyzed = store.analyzed_urls(run_key)
            new_jobs = {
                slug: job
                for slug, job in jobs.items()
                if offer_key(job) not in analyzed
            }
            skipped = len(jobs) - len(new_jobs)
            if skipped:
                logger.info("Skipped %d already-analyzed jobs", skipped)

            if not new_jobs:
                logger.info("No new jobs to analyze")
                store.record_run(
                    run_key,
                    args.provider,
                    query,
                    preferences=args.preferences,
                )
                return

            ai = OllamaAIService(preferences=args.preferences or DEFAULT_PREFERENCES)
            try:
                matches = await ai.filter_jobs(new_jobs)
            finally:
                await ai.close()
            logger.info(
                "AI filtering kept %d of %d new jobs", len(matches), len(new_jobs)
            )

            email_sent_at = None
            if matches:
                body = format_jobs(matches)
                to = args.email_to or DEFAULT_EMAIL_TO
                if not to:
                    raise ValueError(
                        "No recipient email configured: set EMAIL_TO in .env or pass --email-to"
                    )
                subject = settings.get(
                    "email", "subject_template", default="{count} matching jobs"
                ).format(count=len(matches))
                gmail = GmailService()
                gmail.send_email(to=to, subject=subject, body=body)
                email_sent_at = utc_now()
                logger.info("Email sent with %d matching jobs to %s", len(matches), to)
            else:
                logger.warning("No matching jobs")

            store.mark_analyzed(
                run_key,
                new_jobs,
                matched_keys=set(matches),
                email_sent_at=email_sent_at,
            )
            store.record_run(
                run_key,
                args.provider,
                query,
                preferences=args.preferences,
                publications=[job.published_at for job in new_jobs.values()],
            )
    except Exception:
        logger.exception("Run failed")
        raise


if __name__ == "__main__":
    asyncio.run(main())
