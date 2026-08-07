import pytest

from src.cli import build_parser, query_from_args
from src.schemas.job import (
    Experience,
    JobCategory,
    WorkMode,
    WorkType,
)


def test_parse_args_builds_query():
    args = build_parser().parse_args(
        [
            "--category",
            "python",
            "--experience",
            "mid",
            "senior",
            "--work-mode",
            "remote",
            "--work-type",
            "full_time",
            "--pub-date",
            "14",
            "--min-salary",
            "10000",
            "--email-to",
            "test@example.com",
        ]
    )

    query = query_from_args(args)

    assert query.job_cat == JobCategory.PYTHON
    assert query.experience == [Experience.MID, Experience.SENIOR]
    assert query.work_mode == [WorkMode.REMOTE]
    assert query.work_type == [WorkType.FULLTIME]
    assert query.pub_date == 14
    assert query.min_salary == 10000
    assert args.email_to == "test@example.com"


def test_parse_args_defaults_to_empty_query():
    args = build_parser().parse_args([])

    query = query_from_args(args)

    assert query.job_cat is None
    assert query.work_mode is None
    assert query.pub_date is None
    assert query.with_salary is False


def test_parse_args_defaults_to_jjit_provider():
    args = build_parser().parse_args([])

    assert args.provider == ["jjit"]


def test_parse_args_sets_provider():
    args = build_parser().parse_args(["--provider", "jjit"])

    assert args.provider == ["jjit"]


def test_parse_args_rejects_unknown_provider():
    with pytest.raises(SystemExit):
        build_parser().parse_args(["--provider", "nope"])


def test_parse_args_rejects_invalid_enum_value():
    with pytest.raises(SystemExit):
        build_parser().parse_args(["--experience", "boss"])
