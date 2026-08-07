from abc import ABC, abstractmethod
from aiohttp import ClientSession
from src.schemas.job import JobOffer, JobQuery

class ListingService(ABC):
    BASE_URL: str
    SUPPORTED_QUERY_FIELDS: frozenset[str] = frozenset()

    def __init__(self, session: ClientSession):
        self.session = session

    def supports(self, field: str) -> bool:
        return field in self.SUPPORTED_QUERY_FIELDS

    @abstractmethod
    async def search(self, query: JobQuery) -> dict[str, JobOffer]:
        pass
