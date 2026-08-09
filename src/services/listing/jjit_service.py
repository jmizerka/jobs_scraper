from src.config import settings
from src.logger import get_logger
from src.schemas.jjit_schema import JJITJob, JJITListing
from src.schemas.job import JobOffer, JobQuery
from src.services.listing.base import ListingService

logger = get_logger(__name__)

class JJITService(ListingService):
    BASE_URL = settings.get(
        "listing", "jjit", "base_url", default="https://justjoin.it/api/candidate-api/"
    )
    LISTING_URL = settings.get(
        "listing", "jjit", "listing_url", default="https://justjoin.it/job-offer/"
    )
    SUPPORTED_QUERY_FIELDS = frozenset(
        {
            "job_cat",
            "work_mode",
            "work_type",
            "experience",
            "contract_type",
            "lang",
            "city",
            "city_radius",
            "pub_date",
            "with_salary",
            "min_salary",
        }
    )

    async def search(self, query: JobQuery) -> dict[str, JobOffer]:
        query_str = self.parse_query(query)
        logger.debug("JJIT search query: %s", query_str)
        listings = []
        start = 0
        while True:
            url = f"{self.BASE_URL}/{query_str}&from={start}&itemsCount=1500"
            async with self.session.get(url) as resp:
                result = await resp.json()
            page = result.get("data", [])
            if not page:
                break
            listings.extend(JJITListing.model_validate(item) for item in page)
            next_page = (result.get("meta") or {}).get("next") or {}
            if next_page.get("cursor") is None:
                break
            start = next_page["cursor"]
        slugs = [listing.slug for listing in listings]
        jobs = await self._get_jobs(slugs)
        logger.debug("Fetched %d jobs from jjit", len(jobs))
        return {slug: self.to_job_offer(job) for slug, job in jobs.items()}

    async def _get_jobs(self, slugs: list[str]) -> dict[str, JJITJob]:
        jobs = {}
        for slug in slugs:
            async with self.session.get(f"{self.BASE_URL}offers/{slug}") as resp:
                data = await resp.json()
            data["listing_url"] = f"{self.LISTING_URL}{slug}"
            jobs[slug] = JJITJob.model_validate(data)
        return jobs

    @classmethod
    def to_job_offer(cls, job: JJITJob) -> JobOffer:
        salary_min, salary_max, currency, period = cls._extract_salary(job.employmentTypes)
        return JobOffer(
            id=job.id or job.slug,
            title=job.title,
            company=job.companyName,
            url=job.listing_url,
            description=job.body,
            required_skills=[skill.name for skill in job.requiredSkills],
            nice_to_have_skills=[skill.name for skill in job.niceToHaveSkills],
            salary_min=salary_min,
            salary_max=salary_max,
            salary_currency=currency,
            salary_period=period,
            experience_level=job.experienceLevel,
            work_mode=job.workplaceType,
            published_at=job.publishedAt,
            languages=[item.get("code") for item in (job.languages or []) if item.get("code")],
            source="jjit",
            raw=job.model_dump(),
        )

    @staticmethod
    def _extract_salary(employment_types):
        for employment_type in employment_types or []:
            salary = employment_type.get("salary") or {}
            if salary.get("from") is not None or salary.get("to") is not None:
                return (
                    salary.get("from"),
                    salary.get("to"),
                    salary.get("currency"),
                    salary.get("period"),
                )
        return None, None, None, None

    @staticmethod
    def parse_query(query: JobQuery) -> str:
        params = []
        if query.city:
            params.append(f"city={query.city}")
            if query.city_radius:
                params.append(f"cityRadius={query.city_radius}")
        if query.job_cat:
            params.append(f"categories={query.job_cat.value}")
        if query.with_salary:
            params.append("withSalary=true")
        if query.contract_type:
            for ct in query.contract_type:
                params.append(f"employmentTypes={ct.value}")
        if query.work_mode:
            for wm in query.work_mode:
                params.append(f"remoteWorkOptions={wm.value}")
        if query.work_type:
            for wt in query.work_type:
                params.append(f"workingTimes={wt.value}")
        if query.experience:
            for exp in query.experience:
                params.append(f"experienceLevels={exp.value}")
        if query.min_salary:
            params.append(f"minSalary={query.min_salary}")
        if query.pub_date:
            params.append(f"PublishedSinceDays={query.pub_date}")
        if query.lang:
            for lang in query.lang:
                params.append(f"languages={lang.value}")
        params.append("sortBy=publishedAt")
        params.append("orderBy=descending")
        return "offers?" + "&".join(params)
