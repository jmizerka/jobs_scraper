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

DEFAULT_EMAIL_TO = settings.get_env("EMAIL_TO")
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
    logger.info("Run started; providers=%s query=%s", args.provider, query.model_dump())

    try:
        async with ClientSession() as session:
            jobs = await collect_jobs(session, args.provider, query)
        logger.info("Collected %d jobs", len(jobs))

        ai = OllamaAIService(preferences=args.preferences or DEFAULT_PREFERENCES)
        try:
            matches = await ai.filter_jobs(jobs)
        finally:
            await ai.close()
        logger.info("AI filtering kept %d of %d jobs", len(matches), len(jobs))

        if not matches:
            logger.warning("No matching jobs")
            return

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
        logger.info("Email sent with %d matching jobs to %s", len(matches), to)
    except Exception:
        logger.exception("Run failed")
        raise


if __name__ == "__main__":
    asyncio.run(main())
