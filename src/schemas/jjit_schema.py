from pydantic import BaseModel, Field
from typing import Optional


class JJITSkill(BaseModel):
    name: str
    level: Optional[int] = None


class JJITCategory(BaseModel):
    key: str
    parentKey: Optional[str] = None


class JJITListing(BaseModel):
    slug: str
    title: Optional[str] = None
    companyName: Optional[str] = None


class JJITJob(BaseModel):
    id: Optional[str] = None
    slug: Optional[str] = None
    title: Optional[str] = None
    experienceLevel: Optional[str] = None
    category: Optional[JJITCategory] = None
    companyName: Optional[str] = None
    companyUrl: Optional[str] = None
    body: Optional[str] = None
    workplaceType: Optional[str] = None
    workingTime: Optional[str] = None
    publishedAt: Optional[str] = None
    requiredSkills: list[JJITSkill] = Field(default_factory=list)
    niceToHaveSkills: list[JJITSkill] = Field(default_factory=list)
    employmentTypes: Optional[list[dict]] = None
    locations: Optional[list[dict]] = None
    languages: Optional[list[dict]] = None
    listing_url: Optional[str] = None
