from src.schemas.jjit_schema import JJITJob
from src.schemas.job import (
    ContractType,
    Experience,
    JobCategory,
    JobLang,
    JobQuery,
    WorkMode,
    WorkType,
)
from src.services.listing.jjit_service import JJITService

JJITService.BASE_URL = "https://justjoin.it/api/candidate-api/"


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

    def get(self, url):
        self.requested.append(url)
        for key, payload in self.responses.items():
            if url.startswith(key):
                return FakeResponse(payload)
        return FakeResponse({})


def build_session(search_payload=None, detail_payloads=None):
    responses = {}
    if search_payload is not None:
        responses["https://justjoin.it/api/candidate-api//offers?"] = search_payload
    for slug, payload in (detail_payloads or {}).items():
        responses[f"https://justjoin.it/api/candidate-api/offers/{slug}"] = payload
    return FakeSession(responses)


def test_parse_query_no_filters():
    query = JobQuery()
    assert (
        JJITService.parse_query(query)
        == "offers?sortBy=publishedAt&orderBy=descending"
    )


def test_parse_query_city_with_radius():
    query = JobQuery(city="Kraków", city_radius=30)
    assert "city=Kraków" in JJITService.parse_query(query)
    assert "cityRadius=30" in JJITService.parse_query(query)


def test_parse_query_single_category_and_salary():
    query = JobQuery(job_cat=JobCategory.PYTHON, with_salary=True)
    parsed = JJITService.parse_query(query)
    assert "categories=python" in parsed
    assert "withSalary=true" in parsed


def test_parse_query_lists_produce_repeated_params():
    query = JobQuery(
        work_mode=[WorkMode.REMOTE, WorkMode.HYBRID],
        work_type=[WorkType.FULLTIME, WorkType.PARTTIME],
        experience=[Experience.JUNIOR, Experience.MID],
        contract_type=[ContractType.B2B, ContractType.PERMANENT],
        lang=[JobLang.PL, JobLang.EN],
    )
    parsed = JJITService.parse_query(query)
    assert parsed.count("remoteWorkOptions=remote") == 1
    assert parsed.count("remoteWorkOptions=hybrid") == 1
    assert parsed.count("workingTimes=full_time") == 1
    assert parsed.count("workingTimes=part_time") == 1
    assert parsed.count("experienceLevels=junior") == 1
    assert parsed.count("experienceLevels=mid") == 1
    assert parsed.count("employmentTypes=b2b") == 1
    assert parsed.count("employmentTypes=permanent") == 1
    assert parsed.count("languages=pl") == 1
    assert parsed.count("languages=en") == 1


def test_parse_query_min_salary_and_pub_date():
    query = JobQuery(min_salary=10000, pub_date=14)
    parsed = JJITService.parse_query(query)
    assert "minSalary=10000" in parsed
    assert "PublishedSinceDays=14" in parsed


async def test_get_jobs_fetches_detail_and_adds_listing_url():
    slugs = ["job-one", "job-two"]
    session = build_session(
        detail_payloads={
            "job-one": {"id": "guid-1"},
            "job-two": {"id": "guid-2"},
        }
    )
    service = JJITService(session)

    jobs = await service._get_jobs(slugs)

    assert jobs["job-one"].id == "guid-1"
    assert jobs["job-one"].listing_url == "https://justjoin.it/job-offer/job-one"
    assert jobs["job-two"].id == "guid-2"
    assert jobs["job-two"].listing_url == "https://justjoin.it/job-offer/job-two"
    assert session.requested == [
        "https://justjoin.it/api/candidate-api/offers/job-one",
        "https://justjoin.it/api/candidate-api/offers/job-two",
    ]


async def test_search_returns_combined_jobs():
    search_payload = {
        "data": [
            {"slug": "job-one"},
            {"slug": "job-two"},
        ]
    }
    detail_payloads = {
        "job-one": {"title": "First"},
        "job-two": {"title": "Second"},
    }
    session = build_session(search_payload, detail_payloads)
    service = JJITService(session)

    jobs = await service.search(JobQuery())

    assert jobs["job-one"].title == "First"
    assert jobs["job-one"].url == "https://justjoin.it/job-offer/job-one"
    assert jobs["job-one"].source == "jjit"
    assert jobs["job-two"].title == "Second"
    assert jobs["job-two"].url == "https://justjoin.it/job-offer/job-two"
    assert jobs["job-two"].source == "jjit"


def test_to_job_offer_maps_common_fields():
    jj = JJITJob.model_validate(
        {
            "id": "guid-1",
            "slug": "job-one",
            "title": "Python Dev",
            "companyName": "Acme",
            "listing_url": "https://justjoin.it/job-offer/job-one",
            "body": "Some description",
            "workplaceType": "remote",
            "experienceLevel": "mid",
            "publishedAt": "2026-01-01",
            "requiredSkills": [{"name": "Python", "level": 3}],
            "niceToHaveSkills": [{"name": "Java", "level": 2}],
            "languages": [{"code": "pl", "name": "Polski"}],
        }
    )

    offer = JJITService.to_job_offer(jj)

    assert offer.id == "guid-1"
    assert offer.title == "Python Dev"
    assert offer.company == "Acme"
    assert offer.url == "https://justjoin.it/job-offer/job-one"
    assert offer.description == "Some description"
    assert offer.required_skills == ["Python"]
    assert offer.nice_to_have_skills == ["Java"]
    assert offer.experience_level == "mid"
    assert offer.work_mode == "remote"
    assert offer.published_at == "2026-01-01"
    assert offer.languages == ["pl"]
    assert offer.source == "jjit"
    assert offer.raw["id"] == "guid-1"


def test_to_job_offer_extracts_salary():
    jj = JJITJob.model_validate(
        {
            "slug": "job-one",
            "employmentTypes": [
                {
                    "type": "b2b",
                    "salary": {
                        "from": 12000,
                        "to": 16000,
                        "currency": "pln",
                        "period": "monthly",
                    },
                }
            ],
        }
    )

    offer = JJITService.to_job_offer(jj)

    assert offer.salary_min == 12000
    assert offer.salary_max == 16000
    assert offer.salary_currency == "pln"
    assert offer.salary_period == "monthly"


def test_to_job_offer_salary_none_when_missing():
    jj = JJITJob.model_validate({"slug": "job-one"})

    offer = JJITService.to_job_offer(jj)

    assert offer.salary_min is None
    assert offer.salary_max is None
    assert offer.salary_currency is None
    assert offer.salary_period is None


def test_supports_all_query_fields():
    service = JJITService(session=None)

    assert service.supports("lang")
    assert service.supports("min_salary")
    assert service.supports("job_cat")
    assert service.supports("pub_date")
