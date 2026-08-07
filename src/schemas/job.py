from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class JobCategory(Enum):
    AI="ai"
    JS="javascript"
    HTML="html"
    PHP="php"
    RUBY="ruby"
    PYTHON="python"
    JAVA="java"
    NET="net"
    SCALA="scala"
    C="c"
    MOBILE="mobile"
    TESTING="testing"
    DEVOPS="devops"
    ADMIN="admin"
    UX="ux"
    PM="pm"
    GAME="game"
    ANALYTICS="analytics"
    SECURITY="security"
    DATA="data"
    GO="go"
    SUPPORT="support"
    ERP="erp"
    ARCHITECTURE="architecture"
    OTHER="other"

class WorkMode(Enum):
    REMOTE="remote"
    HYBRID="hybrid"
    OFFICE="office"

class ContractType(Enum):
    B2B="b2b"
    PERMANENT="permanent"
    INTERNSHIP="internship"
    MANDATE="mandate-contract"
    TASK="specific-task-contract"

class WorkType(Enum):
    FULLTIME="full_time"
    PARTTIME="part_time"
    PRACTICE="practice_internship"
    FREELANCE="freelance"
    B2B="b2b_contract"

class Experience(Enum):
    INTERN="intern"
    JUNIOR="junior"
    MID="mid"
    SENIOR="senior"
    TEAM_LEADER="team-leader-manager"
    CLEVEL="c-level"

class JobLang(Enum):
    PL="pl"
    EN="en"
    DE="de"
    ES="es"
    UA="ua"
    FR="fr"
    IT="it"
    RU="ru"


class JobQuery(BaseModel):
    job_cat: Optional[JobCategory] = None
    work_mode: Optional[list[WorkMode]] = None
    work_type: Optional[list[WorkType]] = None
    experience: Optional[list[Experience]] = None
    contract_type: Optional[list[ContractType]] = None
    lang: Optional[list[JobLang]] = None
    city: Optional[str] = None
    city_radius: Optional[int] = None
    pub_date: Optional[int] = None
    with_salary: Optional[bool] = None
    min_salary: Optional[int] = None

    def active_fields(self) -> set[str]:
        active = set()
        for name, value in self.model_dump().items():
            if value is None or value is False:
                continue
            if isinstance(value, (list, str)) and not value:
                continue
            active.add(name)
        return active


class JobOffer(BaseModel):
    id: Optional[str] = None
    title: Optional[str] = None
    company: Optional[str] = None
    url: Optional[str] = None
    description: Optional[str] = None
    required_skills: list[str] = Field(default_factory=list)
    nice_to_have_skills: list[str] = Field(default_factory=list)
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_currency: Optional[str] = None
    salary_period: Optional[str] = None
    experience_level: Optional[str] = None
    work_mode: Optional[str] = None
    published_at: Optional[str] = None
    languages: list[str] = Field(default_factory=list)
    source: str
    raw: dict = Field(default_factory=dict)
