from src.schemas.job import JobOffer
from src.services.deterministic_filter import DeterministicFilter


def job(**kwargs) -> JobOffer:
    return JobOffer.model_validate({"source": "test", **kwargs})


def test_rejects_excluded_required_skill():
    filt = DeterministicFilter({"excluded_skills": ["Java"]})
    jj = job(title="Java Dev", required_skills=["Java"])

    assert filt.has_excluded_required_skill(jj) is True


def test_keeps_excluded_nice_to_have_skill():
    filt = DeterministicFilter({"excluded_skills": ["Java"]})
    jj = job(
        title="Python Dev",
        required_skills=["Python"],
        nice_to_have_skills=["Java"],
    )

    assert filt.has_excluded_required_skill(jj) is False


def test_exact_name_match_java_not_javascript():
    filt = DeterministicFilter({"excluded_skills": ["Java"]})
    jj = job(title="JS Dev", required_skills=["JavaScript"])

    assert filt.has_excluded_required_skill(jj) is False


def test_no_excluded_skills_skips_check():
    filt = DeterministicFilter({})
    jj = job(title="Java Dev", required_skills=["Java"])

    assert filt.has_excluded_required_skill(jj) is False
