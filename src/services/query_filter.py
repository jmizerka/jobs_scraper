from datetime import datetime, timedelta, timezone

from src.logger import get_logger
from src.schemas.job import JobQuery

logger = get_logger(__name__)


def _filter_lang(jobs: dict, query: JobQuery) -> dict:
    requested = {lang.value for lang in query.lang or []}
    if not requested:
        return jobs
    filtered = {}
    for slug, job in jobs.items():
        if not job.languages or set(job.languages) & requested:
            filtered[slug] = job
    return filtered


def _filter_work_mode(jobs: dict, query: JobQuery) -> dict:
    requested = {mode.value for mode in query.work_mode or []}
    if not requested:
        return jobs
    filtered = {}
    for slug, job in jobs.items():
        if not job.work_mode or job.work_mode.lower() in requested:
            filtered[slug] = job
    return filtered


def _filter_min_salary(jobs: dict, query: JobQuery) -> dict:
    min_salary = query.min_salary
    if not min_salary:
        return jobs
    filtered = {}
    for slug, job in jobs.items():
        if job.salary_max is None or job.salary_max >= min_salary:
            filtered[slug] = job
    return filtered


def _parse_published_at(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _filter_pub_date(jobs: dict, query: JobQuery) -> dict:
    days = query.pub_date
    if not days:
        return jobs
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    filtered = {}
    for slug, job in jobs.items():
        published = _parse_published_at(job.published_at)
        if published is None:
            filtered[slug] = job
            continue
        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
        if published >= cutoff:
            filtered[slug] = job
    return filtered


QUERY_FIELD_FILTERS = {
    "lang": _filter_lang,
    "work_mode": _filter_work_mode,
    "min_salary": _filter_min_salary,
    "pub_date": _filter_pub_date,
}


def apply_client_filters(
    jobs: dict, query: JobQuery, fields: set[str], provider: str
) -> dict:
    filtered = jobs
    for field in fields:
        handler = QUERY_FIELD_FILTERS.get(field)
        if handler is None:
            logger.warning(
                "Provider '%s' cannot apply filter '%s'; results may not honor it",
                provider,
                field,
            )
            continue
        filtered = handler(filtered, query)
    return filtered
