from datetime import datetime, timezone

from src.config import settings
from src.logger import get_logger
from src.schemas.job import JobOffer, JobQuery
from src.schemas.nfjobs_schema import NFJobsJob, NFJobsListing
from src.services.listing.base import ListingService

logger = get_logger(__name__)

class NFJobsService(ListingService):
    BASE_URL = settings.get(
        "listing", "nfjobs", "base_url", default="https://nofluffjobs.com/api/"
    )
    PAGE_SIZE = settings.get("listing", "nfjobs", "page_size", default=20)
    SEARCH_PARAMS = settings.get(
        "listing",
        "nfjobs",
        "search_params",
        default=[
            ["pageFrom", "1"],
            ["pageTo", "1"],
            ["pageSize", "20"],
            ["withSalaryMatch", "true"],
            ["salaryCurrency", "PLN"],
            ["salaryPeriod", "month"],
            ["region", "pl"],
            ["language", "pl-PL"],
            ["sort", "newest"],
        ],
    )
    DETAIL_QUERY = settings.get(
        "listing",
        "nfjobs",
        "detail_query",
        default="region=pl&salaryCurrency=PLN&salaryPeriod=month&language=pl-PL",
    )
    URL_TEMPLATE = settings.get(
        "listing",
        "nfjobs",
        "url_template",
        default="https://nofluffjobs.com/pl/job/{url}",
    )

    SUPPORTED_QUERY_FIELDS = frozenset(
        {
            "job_cat",
            "work_mode",
            "experience",
            "contract_type",
            "lang",
            "city",
            "with_salary",
        }
    )

    WORK_MODE_MORE = {
        "remote": "remote",
        "hybrid": "hybrid",
        "office": "onsite",
    }

    EXPERIENCE_SENIORITY = {
        "intern": "Trainee",
        "junior": "Junior",
        "mid": "Mid",
        "senior": "Senior",
    }

    CONTRACT_EMPLOYMENT = {
        "b2b": "b2b",
        "permanent": "permanent",
    }

    REMOTE_WORK_MODE = {
        5: "remote",
        2: "hybrid",
        0: "office",
    }

    SEARCH_URL = (
        f"{BASE_URL}search/posting?"
        + "&".join(f"{key}={value}" for key, value in SEARCH_PARAMS)
    )

    async def search(self, query: JobQuery) -> dict[str, JobOffer]:
        payload = self.build_payload(query)
        logger.debug("NFJobs search payload: %s", payload)
        async with self.session.post(self.SEARCH_URL, json=payload) as resp:
            result = await resp.json()
        listings = [NFJobsListing.model_validate(item) for item in result["postings"]]
        references = [listing.reference for listing in listings]
        jobs = await self._get_jobs(references, listings)
        logger.debug("Fetched %d jobs from nfjobs", len(jobs))
        return {ref: self.to_job_offer(job) for ref, job in jobs.items()}

    async def _get_jobs(
        self, references: list[str], listings: list[NFJobsListing] | None = None
    ) -> dict[str, NFJobsJob]:
        listing_by_ref = {listing.reference: listing for listing in listings or []}
        jobs = {}
        for ref in references:
            async with self.session.get(
                f"{self.BASE_URL}posting/{ref}?{self.DETAIL_QUERY}"
            ) as resp:
                data = await resp.json()
            listing = listing_by_ref.get(ref)
            if listing is not None:
                data["listing_url"] = self.URL_TEMPLATE.format(url=listing.url)
                data["fullyRemote"] = listing.fullyRemote
            jobs[ref] = NFJobsJob.model_validate(data)
        return jobs

    @classmethod
    def to_job_offer(cls, job: NFJobsJob) -> JobOffer:
        salary_min, salary_max, currency, period = cls._extract_salary(job)
        requirements = job.requirements
        return JobOffer(
            id=job.reference or job.id,
            title=job.title,
            company=job.company.name if job.company else None,
            url=job.listing_url
            or (cls.URL_TEMPLATE.format(url=job.postingUrl) if job.postingUrl else None),
            description=job.details.description if job.details else None,
            required_skills=[
                item.value for item in (requirements.musts if requirements else []) if item.value
            ],
            nice_to_have_skills=[
                item.value for item in (requirements.nices if requirements else []) if item.value
            ],
            salary_min=salary_min,
            salary_max=salary_max,
            salary_currency=currency,
            salary_period=period,
            experience_level=(
                ", ".join(job.basics.seniority)
                if job.basics and job.basics.seniority
                else None
            ),
            work_mode=cls._work_mode(job),
            published_at=cls._published_at(job.posted),
            languages=[
                item.code
                for item in (requirements.languages if requirements else [])
                if item.code
            ],
            source="nfjobs",
            raw=job.model_dump(),
        )

    @staticmethod
    def _extract_salary(job: NFJobsJob):
        essentials = job.essentials
        if essentials is None:
            return None, None, None, None
        for salary in (essentials.originalSalary, essentials.convertedSalary):
            if salary is None:
                continue
            for item in (salary.types or {}).values():
                if item.range and any(item.range):
                    return (
                        int(item.range[0]),
                        int(item.range[-1]),
                        salary.currency,
                        item.period.lower() if item.period else None,
                    )
        return None, None, None, None

    @classmethod
    def _work_mode(cls, job: NFJobsJob) -> str:
        if job.fullyRemote:
            return "remote"
        location = job.location
        if location and location.remote in cls.REMOTE_WORK_MODE:
            return cls.REMOTE_WORK_MODE[location.remote]
        if location and location.remoteFlexible:
            return "hybrid"
        return "office"

    @staticmethod
    def _published_at(ms: int | None) -> str | None:
        if not ms:
            return None
        return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()

    @classmethod
    def build_payload(cls, query: JobQuery) -> dict:
        criteria = {
            "city": [],
            "company": [],
            "category": [],
            "country": [],
            "employment": [],
            "seniority": [],
            "requirement": [],
            "salary": [],
            "more": [],
            "applicationStatus": [],
            "keyword": [],
            "jobLanguage": [],
            "jobPosition": [],
            "province": [],
            "id": [],
            "withSalaryMatch": [],
        }
        if query.job_cat:
            criteria["category"].append(query.job_cat.value)
        if query.work_mode:
            for wm in query.work_mode:
                more = cls.WORK_MODE_MORE.get(wm.value)
                if more:
                    criteria["more"].append(more)
        if query.experience:
            for exp in query.experience:
                seniority = cls.EXPERIENCE_SENIORITY.get(exp.value)
                if seniority:
                    criteria["seniority"].append(seniority)
        if query.contract_type:
            for ct in query.contract_type:
                employment = cls.CONTRACT_EMPLOYMENT.get(ct.value)
                if employment:
                    criteria["employment"].append(employment)
        if query.lang:
            for lang in query.lang:
                criteria["jobLanguage"].append(lang.value)
        if query.city:
            criteria["city"].append(query.city)
        return {
            "criteriaSearch": criteria,
            "pageSize": cls.PAGE_SIZE,
            "withSalaryMatch": bool(query.with_salary),
        }
