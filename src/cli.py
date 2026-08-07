import argparse
from enum import Enum

from src.schemas.job import (
    ContractType,
    Experience,
    JobCategory,
    JobLang,
    JobQuery,
    WorkMode,
    WorkType,
)
from src.services.listing import REGISTRY


def _enum_type(enum_cls: type[Enum]):
    def parse(value: str):
        try:
            return enum_cls(value)
        except ValueError:
            valid = ", ".join(member.value for member in enum_cls)
            raise argparse.ArgumentTypeError(
                f"invalid choice: {value!r} (choose from {valid})"
            ) from None

    parse.__name__ = enum_cls.__name__
    return parse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="job-listings-scraper",
        description="Search job listing services and email matching jobs.",
    )
    parser.add_argument(
        "--provider",
        nargs="+",
        default=["jjit"],
        choices=list(REGISTRY),
        help="Listing service(s) to search, e.g. jjit",
    )
    parser.add_argument(
        "--category",
        type=_enum_type(JobCategory),
        help="Job category, e.g. python, javascript, data",
    )
    parser.add_argument(
        "--work-mode",
        nargs="+",
        type=_enum_type(WorkMode),
        help="Remote work options, e.g. remote hybrid office",
    )
    parser.add_argument(
        "--work-type",
        nargs="+",
        type=_enum_type(WorkType),
        help="Working times, e.g. full_time part_time",
    )
    parser.add_argument(
        "--experience",
        nargs="+",
        type=_enum_type(Experience),
        help="Experience levels, e.g. junior mid senior",
    )
    parser.add_argument(
        "--contract-type",
        nargs="+",
        type=_enum_type(ContractType),
        help="Contract types, e.g. b2b permanent",
    )
    parser.add_argument(
        "--lang",
        nargs="+",
        type=_enum_type(JobLang),
        help="Job offer languages, e.g. pl en de",
    )
    parser.add_argument("--city", type=str, help="City to search in")
    parser.add_argument("--city-radius", type=int, help="Search radius in km")
    parser.add_argument("--pub-date", type=int, help="Published within N days")
    parser.add_argument(
        "--with-salary", action="store_true", help="Only offers with salary"
    )
    parser.add_argument("--min-salary", type=int, help="Minimum salary in PLN")
    parser.add_argument("--email-to", help="Recipient email address")
    parser.add_argument(
        "--preferences",
        help="Path to preferences JSON used by the AI matcher",
    )
    return parser


def query_from_args(args: argparse.Namespace) -> JobQuery:
    return JobQuery(
        job_cat=args.category,
        work_mode=args.work_mode,
        work_type=args.work_type,
        experience=args.experience,
        contract_type=args.contract_type,
        lang=args.lang,
        city=args.city,
        city_radius=args.city_radius,
        pub_date=args.pub_date,
        with_salary=args.with_salary,
        min_salary=args.min_salary,
    )
