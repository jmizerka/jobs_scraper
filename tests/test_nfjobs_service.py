from src.schemas.job import (
    ContractType,
    Experience,
    JobCategory,
    JobLang,
    JobQuery,
    WorkMode,
)
from src.schemas.nfjobs_schema import NFJobsJob
from src.services.listing.nfjobs_service import NFJobsService

NFJobsService.BASE_URL = "https://nofluffjobs.com/api/"


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def json(self):
        return self._payload


class FakeSession:
    def __init__(self, responses):
        self.responses = responses
        self.requested = []
        self.requested_payloads = []

    def get(self, url):
        self.requested.append(("GET", url, None))
        for key, payload in self.responses.items():
            if url.startswith(key):
                return FakeResponse(payload)
        return FakeResponse({})

    def post(self, url, json=None):
        self.requested.append(("POST", url, json))
        for key, payload in self.responses.items():
            if url.startswith(key):
                return FakeResponse(payload)
        return FakeResponse({})


def build_session(search_payload=None, detail_payloads=None):
    responses = {}
    if search_payload is not None:
        responses["https://nofluffjobs.com/api/search/posting"] = search_payload
    for ref, payload in (detail_payloads or {}).items():
        responses[f"https://nofluffjobs.com/api/posting/{ref}"] = payload
    return FakeSession(responses)


def test_build_payload_no_filters():
    query = JobQuery()
    payload = NFJobsService.build_payload(query)
    assert payload["criteriaSearch"]["category"] == []
    assert payload["criteriaSearch"]["more"] == []
    assert payload["criteriaSearch"]["seniority"] == []
    assert payload["criteriaSearch"]["employment"] == []
    assert payload["criteriaSearch"]["city"] == []
    assert payload["criteriaSearch"]["jobLanguage"] == []
    assert payload["withSalaryMatch"] is False
    assert payload["pageSize"] == 20


def test_build_payload_maps_all_supported_fields():
    query = JobQuery(
        job_cat=JobCategory.PYTHON,
        work_mode=[WorkMode.REMOTE, WorkMode.HYBRID, WorkMode.OFFICE],
        experience=[Experience.INTERN, Experience.JUNIOR, Experience.MID, Experience.SENIOR],
        contract_type=[ContractType.B2B, ContractType.PERMANENT],
        lang=[JobLang.PL, JobLang.EN],
        city="Kraków",
        with_salary=True,
    )
    criteria = NFJobsService.build_payload(query)["criteriaSearch"]
    assert criteria["category"] == ["python"]
    assert criteria["more"] == ["remote", "hybrid", "onsite"]
    assert criteria["seniority"] == ["Trainee", "Junior", "Mid", "Senior"]
    assert criteria["employment"] == ["b2b", "permanent"]
    assert criteria["jobLanguage"] == ["pl", "en"]
    assert criteria["city"] == ["Kraków"]
    assert NFJobsService.build_payload(query)["withSalaryMatch"] is True


def test_build_payload_skips_unmappable_experience():
    query = JobQuery(experience=[Experience.TEAM_LEADER, Experience.CLEVEL])
    criteria = NFJobsService.build_payload(query)["criteriaSearch"]
    assert criteria["seniority"] == []


async def test_get_jobs_fetches_detail_and_adds_listing_url():
    refs = ["VK1QNPM4", "ZQ92GBVA"]
    session = build_session(
        search_payload={"postings": []},
        detail_payloads={
            "VK1QNPM4": {"reference": "VK1QNPM4"},
            "ZQ92GBVA": {"reference": "ZQ92GBVA"},
        },
    )
    service = NFJobsService(session)

    jobs = await service._get_jobs(refs, [])

    assert jobs["VK1QNPM4"].reference == "VK1QNPM4"
    assert jobs["ZQ92GBVA"].reference == "ZQ92GBVA"
    assert session.requested[0] == (
        "GET",
        "https://nofluffjobs.com/api/posting/VK1QNPM4?region=pl&salaryCurrency=PLN&salaryPeriod=month&language=pl-PL",
        None,
    )


async def test_search_returns_combined_jobs():
    search_payload = {
        "postings": [
            {"reference": "VK1QNPM4", "url": "software-engineer", "fullyRemote": False},
            {"reference": "ZQ92GBVA", "url": "senior-engineer", "fullyRemote": True},
        ]
    }
    detail_payloads = {
        "VK1QNPM4": {"title": "First", "reference": "VK1QNPM4"},
        "ZQ92GBVA": {"title": "Second", "reference": "ZQ92GBVA"},
    }
    session = build_session(search_payload, detail_payloads)
    service = NFJobsService(session)

    jobs = await service.search(JobQuery())

    assert jobs["VK1QNPM4"].title == "First"
    assert jobs["VK1QNPM4"].url == "https://nofluffjobs.com/pl/jobs/software-engineer"
    assert jobs["VK1QNPM4"].source == "nfjobs"
    assert jobs["ZQ92GBVA"].title == "Second"
    assert jobs["ZQ92GBVA"].url == "https://nofluffjobs.com/pl/jobs/senior-engineer"
    assert jobs["ZQ92GBVA"].source == "nfjobs"
    assert session.requested[0][0] == "POST"
    assert session.requested[0][1].startswith(
        "https://nofluffjobs.com/api/search/posting?"
    )
    assert "sort=newest" in session.requested[0][1]


def test_to_job_offer_maps_common_fields():
    job = NFJobsJob.model_validate(
        {
            "reference": "ZQ92GBVA",
            "id": "guid-1",
            "title": "Senior Software Engineer",
            "postingUrl": "senior-engineer-graphcore-gdansk",
            "posted": 1785103231368,
            "company": {"name": "Graphcore"},
            "basics": {"category": "backend", "seniority": ["Senior"], "technology": "Python"},
            "details": {"description": "Some description"},
            "location": {"remote": 5},
            "requirements": {
                "musts": [{"value": "C++", "type": "main"}],
                "nices": [{"value": "Go", "type": "main"}],
                "languages": [{"type": "MUST", "code": "en"}],
            },
            "listing_url": "https://nofluffjobs.com/pl/jobs/senior-engineer-graphcore-gdansk",
        }
    )

    offer = NFJobsService.to_job_offer(job)

    assert offer.id == "ZQ92GBVA"
    assert offer.title == "Senior Software Engineer"
    assert offer.company == "Graphcore"
    assert offer.url == "https://nofluffjobs.com/pl/jobs/senior-engineer-graphcore-gdansk"
    assert offer.description == "Some description"
    assert offer.required_skills == ["C++"]
    assert offer.nice_to_have_skills == ["Go"]
    assert offer.experience_level == "Senior"
    assert offer.work_mode == "remote"
    assert offer.languages == ["en"]
    assert offer.source == "nfjobs"
    assert offer.raw["id"] == "guid-1"


def test_to_job_offer_falls_back_to_posting_url():
    job = NFJobsJob.model_validate(
        {"reference": "ZQ92GBVA", "postingUrl": "senior-engineer-graphcore-gdansk"}
    )

    offer = NFJobsService.to_job_offer(job)

    assert offer.url == "https://nofluffjobs.com/pl/jobs/senior-engineer-graphcore-gdansk"


def test_to_job_offer_extracts_original_salary():
    job = NFJobsJob.model_validate(
        {
            "reference": "ZQ92GBVA",
            "essentials": {
                "originalSalary": {
                    "currency": "PLN",
                    "types": {
                        "permanent": {
                            "period": "Year",
                            "range": [260400.0, 352200.0],
                        }
                    },
                }
            },
        }
    )

    offer = NFJobsService.to_job_offer(job)

    assert offer.salary_min == 260400
    assert offer.salary_max == 352200
    assert offer.salary_currency == "PLN"
    assert offer.salary_period == "year"


def test_to_job_offer_salary_none_when_missing():
    job = NFJobsJob.model_validate({"reference": "ZQ92GBVA"})

    offer = NFJobsService.to_job_offer(job)

    assert offer.salary_min is None
    assert offer.salary_max is None
    assert offer.salary_currency is None
    assert offer.salary_period is None


def test_work_mode_from_remote_flag():
    assert NFJobsService._work_mode(NFJobsJob.model_validate({"fullyRemote": True})) == "remote"
    assert NFJobsService._work_mode(NFJobsJob.model_validate({"location": {"remote": 5}})) == "remote"
    assert NFJobsService._work_mode(NFJobsJob.model_validate({"location": {"remote": 2}})) == "hybrid"
    assert NFJobsService._work_mode(NFJobsJob.model_validate({"location": {"remote": 0}})) == "office"


def test_published_at_converts_millis():
    assert NFJobsService._published_at(1785103231368) == "2026-07-26T22:00:31.368000+00:00"
    assert NFJobsService._published_at(None) is None


def test_supports_all_query_fields():
    service = NFJobsService(session=None)

    assert service.supports("lang")
    assert service.supports("job_cat")
    assert service.supports("work_mode")
    assert service.supports("experience")
    assert service.supports("contract_type")
    assert service.supports("city")
    assert service.supports("with_salary")
    assert not service.supports("min_salary")
    assert not service.supports("pub_date")
