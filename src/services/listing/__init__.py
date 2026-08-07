from src.services.listing.jjit_service import JJITService
from src.services.listing.nfjobs_service import NFJobsService

REGISTRY = {"jjit": JJITService, "nfjobs": NFJobsService}


def get_listing_service(name, session):
    try:
        return REGISTRY[name](session)
    except KeyError:
        raise ValueError(f"Unknown listing provider: {name}") from None
