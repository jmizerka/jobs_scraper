import pytest

import main
from src.schemas.job import JobLang, JobOffer, JobQuery
from src.services.listing import REGISTRY, get_listing_service
from src.services.listing.jjit_service import JJITService


def test_registry_contains_jjit():
    assert REGISTRY["jjit"] is JJITService


def test_get_listing_service_returns_service():
    service = get_listing_service("jjit", session=None)

    assert isinstance(service, JJITService)


def test_get_listing_service_unknown_raises():
    with pytest.raises(ValueError):
        get_listing_service("nope", session=None)


async def test_collect_jobs_aggregates_and_dedupes(monkeypatch):
    jobs_by_provider = {
        "jjit": {"one": JobOffer(source="jjit", title="A", url="https://a/1")},
        "other": {
            "two": JobOffer(source="other", title="B", url="https://a/1"),
            "three": JobOffer(source="other", title="C", url="https://b/2"),
        },
    }

    def fake_get(name, session):
        class FakeService:
            SUPPORTED_QUERY_FIELDS = frozenset()

            async def search(self, query):
                return jobs_by_provider[name]

        return FakeService()

    monkeypatch.setattr(main, "get_listing_service", fake_get)

    jobs = await main.collect_jobs(
        session=None, providers=["jjit", "other"], query=JobQuery()
    )

    assert set(jobs) == {"jjit/one", "other/three"}
    assert jobs["jjit/one"].title == "A"
    assert jobs["other/three"].title == "C"


async def test_collect_jobs_applies_client_fallback(monkeypatch):
    query = JobQuery(lang=[JobLang.PL])
    searched = []

    def fake_get(name, session):
        class FakeService:
            SUPPORTED_QUERY_FIELDS = frozenset()

            async def search(self, query):
                searched.append(name)
                return {
                    "pl": JobOffer(source=name, title="PL", url=f"https://{name}/pl", languages=["pl"]),
                    "en": JobOffer(source=name, title="EN", url=f"https://{name}/en", languages=["en"]),
                }

        return FakeService()

    monkeypatch.setattr(main, "get_listing_service", fake_get)

    jobs = await main.collect_jobs(session=None, providers=["nolang"], query=query)

    assert set(jobs) == {"nolang/pl"}


def test_format_jobs_uses_title_and_url():
    jobs = {
        "a": JobOffer(source="jjit", title="Python Dev", url="https://a/1"),
        "b": JobOffer(source="jjit", title="Data Engineer", url="https://b/2"),
    }

    assert (
        main.format_jobs(jobs)
        == "Python Dev\nhttps://a/1\n\nData Engineer\nhttps://b/2"
    )
