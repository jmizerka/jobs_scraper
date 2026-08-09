from src.schemas.job import JobCategory, JobOffer, JobQuery
from src.services.state import (
    JobStateStore,
    config_key,
    offer_key,
)


def _query(**overrides) -> JobQuery:
    return JobQuery(**overrides)


def _job(url: str | None = "https://example.com/job", job_id: str | None = "x") -> JobOffer:
    return JobOffer(url=url, id=job_id, source="jjit", title="Title")


def test_config_key_is_deterministic():
    query = _query(job_cat=JobCategory.PYTHON, pub_date=7)
    first = config_key(["jjit"], query, preferences=None)
    second = config_key(["jjit"], query, preferences=None)
    assert first == second


def test_config_key_ignores_provider_order():
    query = _query()
    assert config_key(["jjit", "nfjobs"], query) == config_key(
        ["nfjobs", "jjit"], query
    )


def test_config_key_differs_by_provider():
    query = _query()
    assert config_key(["jjit"], query) != config_key(["nfjobs"], query)


def test_config_key_differs_by_query_param():
    assert config_key(["jjit"], _query(job_cat=JobCategory.PYTHON)) != config_key(
        ["jjit"], _query(job_cat=JobCategory.DATA)
    )


def test_config_key_differs_by_preferences():
    query = _query()
    assert config_key(["jjit"], query, preferences="a.json") != config_key(
        ["jjit"], query, preferences="b.json"
    )


def test_offer_key_prefers_url():
    assert offer_key(_job()) == "https://example.com/job"


def test_offer_key_falls_back_to_id():
    assert offer_key(_job(url=None)) == "x"


def test_offer_key_none_without_identity():
    assert offer_key(_job(url=None, job_id=None)) is None


def test_mark_analyzed_then_analyzed_urls(tmp_path):
    store = JobStateStore(tmp_path / "state.db")
    try:
        key = config_key(["jjit"], _query())
        store.mark_analyzed(
            key, {"jjit/x": _job()}, matched_keys={"jjit/x"}, email_sent_at="now"
        )
        assert store.analyzed_urls(key) == {"https://example.com/job"}
        store.mark_analyzed(
            key,
            {"jjit/x": _job(), "jjit/y": _job("https://example.com/job2", "y")},
        )
        assert store.analyzed_urls(key) == {
            "https://example.com/job",
            "https://example.com/job2",
        }
    finally:
        store.close()


def test_analyzed_urls_scoped_to_config(tmp_path):
    store = JobStateStore(tmp_path / "state.db")
    try:
        key_a = config_key(["jjit"], _query(job_cat=JobCategory.PYTHON))
        key_b = config_key(["jjit"], _query(job_cat=JobCategory.DATA))
        store.mark_analyzed(key_a, {"jjit/x": _job()})
        assert store.analyzed_urls(key_b) == set()
    finally:
        store.close()


def test_offers_without_identity_not_tracked(tmp_path):
    store = JobStateStore(tmp_path / "state.db")
    try:
        key = config_key(["jjit"], _query())
        store.mark_analyzed(key, {"jjit/x": _job(url=None, job_id=None)})
        assert store.analyzed_urls(key) == set()
    finally:
        store.close()


def test_record_run_inserts_and_updates(tmp_path):
    store = JobStateStore(tmp_path / "state.db")
    try:
        key = config_key(["jjit"], _query(pub_date=7))
        store.record_run(
            key,
            ["jjit"],
            _query(pub_date=7),
            preferences=None,
            publications=["2026-08-01T10:00:00+00:00", "2026-08-05T10:00:00+00:00"],
        )
        run = store.get_run(key)
        assert run["first_run_at"] == run["last_run_at"]
        assert run["last_success_at"] == run["last_run_at"]
        assert run["last_publication_seen_at"] == "2026-08-05T10:00:00+00:00"

        store.record_run(
            key,
            ["jjit"],
            _query(pub_date=7),
            publications=["2026-08-01T10:00:00+00:00"],
        )
        run = store.get_run(key)
        assert run["first_run_at"] <= run["last_run_at"]
        assert run["last_publication_seen_at"] == "2026-08-05T10:00:00+00:00"
    finally:
        store.close()


def test_record_run_failure_keeps_last_success(tmp_path):
    store = JobStateStore(tmp_path / "state.db")
    try:
        key = config_key(["jjit"], _query())
        store.record_run(key, ["jjit"], _query(), success=True)
        first_success = store.get_run(key)["last_success_at"]
        store.record_run(key, ["jjit"], _query(), success=False)
        run = store.get_run(key)
        assert run["last_success_at"] == first_success
        assert run["last_run_at"] != run["last_success_at"]
    finally:
        store.close()


def test_last_publication_ignores_unparseable(tmp_path):
    store = JobStateStore(tmp_path / "state.db")
    try:
        key = config_key(["jjit"], _query())
        store.record_run(
            key, ["jjit"], _query(), publications=[None, "not-a-date"]
        )
        assert store.get_run(key)["last_publication_seen_at"] is None
    finally:
        store.close()
