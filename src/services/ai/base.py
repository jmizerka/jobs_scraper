from abc import ABC, abstractmethod

from src.schemas.job import JobOffer
from src.services.deterministic_filter import DeterministicFilter


class AIService(ABC):
    def __init__(self, preferences=None):
        self.deterministic_filter = DeterministicFilter(preferences)

    @property
    def preferences(self) -> dict:
        return self.deterministic_filter.preferences

    async def filter_jobs(self, jobs: dict) -> dict:
        matches = {}
        for slug, job in jobs.items():
            if await self.matches(job):
                matches[slug] = job
        return matches

    @abstractmethod
    async def matches(self, job: JobOffer) -> bool:
        pass

    @abstractmethod
    async def close(self):
        pass
