from src.schemas.job import JobCategory, JobLang, JobOffer, JobQuery, WorkMode
from src.services.query_filter import apply_client_filters


def offer(**kwargs) -> JobOffer:
    return JobOffer.model_validate({"source": "test", **kwargs})


def test_active_fields_empty_query():
    assert JobQuery().active_fields() == set()


def test_active_fields_includes_set_values():
    query = JobQuery(job_cat=JobCategory.PYTHON, with_salary=True, pub_date=14)

    assert query.active_fields() == {"job_cat", "with_salary", "pub_date"}


def test_active_fields_excludes_defaults():
    query = JobQuery(work_mode=[], min_salary=None, with_salary=False)

    assert query.active_fields() == set()


def test_filter_lang_keeps_overlapping_and_unknown():
    query = JobQuery(lang=[JobLang.PL])
    jobs = {
        "pl": offer(languages=["pl", "en"]),
        "en": offer(languages=["en"]),
        "unknown": offer(languages=[]),
    }

    filtered = apply_client_filters(jobs, query, {"lang"}, provider="test")

    assert set(filtered) == {"pl", "unknown"}


def test_filter_work_mode():
    query = JobQuery(work_mode=[WorkMode.REMOTE])
    jobs = {
        "remote": offer(work_mode="remote"),
        "hybrid": offer(work_mode="hybrid"),
        "unknown": offer(work_mode=None),
    }

    filtered = apply_client_filters(jobs, query, {"work_mode"}, provider="test")

    assert set(filtered) == {"remote", "unknown"}


def test_filter_min_salary_drops_only_below_range():
    query = JobQuery(min_salary=10000)
    jobs = {
        "above": offer(salary_min=12000, salary_max=16000),
        "below": offer(salary_min=5000, salary_max=8000),
        "unknown": offer(salary_min=None, salary_max=None),
    }

    filtered = apply_client_filters(jobs, query, {"min_salary"}, provider="test")

    assert set(filtered) == {"above", "unknown"}


def test_unhandled_field_warns(caplog):
    query = JobQuery(city="Warsaw")
    jobs = {"a": offer(title="A")}

    filtered = apply_client_filters(jobs, query, {"city"}, provider="no-city")

    assert filtered == jobs
    assert any("cannot apply filter 'city'" in record.message for record in caplog.records)


def test_multiple_unsupported_fields_all_applied():
    query = JobQuery(lang=[JobLang.PL], min_salary=10000)
    jobs = {
        "keep": offer(languages=["pl"], salary_max=12000),
        "drop-lang": offer(languages=["en"], salary_max=12000),
        "drop-salary": offer(languages=["pl"], salary_max=8000),
    }

    filtered = apply_client_filters(
        jobs, query, {"lang", "min_salary"}, provider="test"
    )

    assert set(filtered) == {"keep"}


def test_filter_pub_date_keeps_recent_and_unknown():
    from datetime import datetime, timezone, timedelta

    days_ago = lambda n: (datetime.now(timezone.utc) - timedelta(days=n)).isoformat()
    query = JobQuery(pub_date=60)
    jobs = {
        "recent-iso": offer(published_at=days_ago(1)),
        "recent-date": offer(published_at=days_ago(1).split("T")[0]),
        "old": offer(published_at=days_ago(120)),
        "unknown": offer(published_at=None),
        "garbage": offer(published_at="not-a-date"),
    }

    filtered = apply_client_filters(jobs, query, {"pub_date"}, provider="test")

    assert set(filtered) == {"recent-iso", "recent-date", "unknown", "garbage"}


def test_filter_pub_date_drops_older_than_cutoff():
    from datetime import datetime, timezone, timedelta

    days_ago = lambda n: (datetime.now(timezone.utc) - timedelta(days=n)).isoformat()
    query = JobQuery(pub_date=7)
    jobs = {
        "today": offer(published_at=days_ago(0)),
        "six_days_ago": offer(published_at=days_ago(6)),
        "eight_days_ago": offer(published_at=days_ago(8)),
    }

    filtered = apply_client_filters(jobs, query, {"pub_date"}, provider="test")

    assert set(filtered) == {"today", "six_days_ago"}

