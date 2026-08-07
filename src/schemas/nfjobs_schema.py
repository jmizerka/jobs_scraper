from pydantic import BaseModel, Field
from typing import Optional


class NFJobsLocationPlace(BaseModel):
    city: Optional[str] = None
    url: Optional[str] = None


class NFJobsListingLocation(BaseModel):
    places: list[NFJobsLocationPlace] = Field(default_factory=list)
    fullyRemote: Optional[bool] = None


class NFJobsListing(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    title: Optional[str] = None
    reference: Optional[str] = None
    url: Optional[str] = None
    category: Optional[str] = None
    seniority: list[str] = Field(default_factory=list)
    salary: Optional[dict] = None
    posted: Optional[int] = None
    renewed: Optional[int] = None
    fullyRemote: Optional[bool] = None
    location: Optional[NFJobsListingLocation] = None


class NFJobsCompany(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    size: Optional[str] = None


class NFJobsRequirementItem(BaseModel):
    value: Optional[str] = None
    type: Optional[str] = None


class NFJobsLanguage(BaseModel):
    type: Optional[str] = None
    code: Optional[str] = None


class NFJobsSalaryType(BaseModel):
    period: Optional[str] = None
    range: list[float] = Field(default_factory=list)
    paidHoliday: Optional[bool] = None


class NFJobsSalary(BaseModel):
    currency: Optional[str] = None
    types: dict[str, NFJobsSalaryType] = Field(default_factory=dict)
    disclosedAt: Optional[str] = None
    flexibleUpperBound: Optional[bool] = None


class NFJobsLocation(BaseModel):
    places: list[NFJobsLocationPlace] = Field(default_factory=list)
    remote: Optional[int] = None
    remoteFlexible: Optional[bool] = None
    multicityCount: Optional[int] = None
    fullyRemote: Optional[bool] = None


class NFJobsBasics(BaseModel):
    category: Optional[str] = None
    seniority: list[str] = Field(default_factory=list)
    technology: Optional[str] = None


class NFJobsDetails(BaseModel):
    description: Optional[str] = None


class NFJobsEssentials(BaseModel):
    originalSalary: Optional[NFJobsSalary] = None
    convertedSalary: Optional[NFJobsSalary] = None


class NFJobsRequirements(BaseModel):
    musts: list[NFJobsRequirementItem] = Field(default_factory=list)
    nices: list[NFJobsRequirementItem] = Field(default_factory=list)
    languages: list[NFJobsLanguage] = Field(default_factory=list)


class NFJobsRecruitment(BaseModel):
    languages: list[NFJobsLanguage] = Field(default_factory=list)
    processSteps: list[str] = Field(default_factory=list)


class NFJobsJob(BaseModel):
    id: Optional[str] = None
    reference: Optional[str] = None
    title: Optional[str] = None
    postingUrl: Optional[str] = None
    defaultUrl: Optional[str] = None
    posted: Optional[int] = None
    company: Optional[NFJobsCompany] = None
    basics: Optional[NFJobsBasics] = None
    details: Optional[NFJobsDetails] = None
    location: Optional[NFJobsLocation] = None
    essentials: Optional[NFJobsEssentials] = None
    requirements: Optional[NFJobsRequirements] = None
    recruitment: Optional[NFJobsRecruitment] = None
    benefits: Optional[dict] = None
    listing_url: Optional[str] = None
    fullyRemote: Optional[bool] = None
