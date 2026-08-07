from src.schemas.job import JobOffer
from src.services.ai import OllamaAIService
from src.services.ai.ollama import MATCH_SCHEMA


def job(**kwargs) -> JobOffer:
    return JobOffer.model_validate({"source": "test", **kwargs})


class FakeAIResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status = status

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def json(self):
        return self._payload


class FakeAISession:
    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def post(self, url, json=None):
        self.calls.append(json)
        item = self.results.pop(0)
        if isinstance(item, FakeAIResponse):
            return item
        if isinstance(item, tuple):
            payload, status = item
            return FakeAIResponse(payload, status=status)
        return FakeAIResponse(item)


def build_service(results, preferences=None, max_attempts=3, fallback="include"):
    return OllamaAIService(
        preferences=preferences or {},
        session=FakeAISession(results),
        max_attempts=max_attempts,
        fallback=fallback,
    )


async def test_filter_jobs_keeps_only_matches():
    service = build_service(
        results=[
            {"message": {"content": '{"match": false}'}},
            {"message": {"content": '{"match": true}'}},
        ],
        preferences={"skills": ["Python"]},
    )
    jobs = {
        "no-match": job(title="PHP Dev"),
        "yes-match": job(title="Python Dev"),
    }

    assert await service.filter_jobs(jobs) == {"yes-match": job(title="Python Dev")}
    assert len(service.session.calls) == 2


async def test_payload_sends_json_schema_and_temperature():
    service = build_service(results=[{"message": {"content": '{"match": true}'}}])

    assert await service.matches(job(title="X")) is True
    assert service.session.calls[0]["format"] == MATCH_SCHEMA
    assert service.session.calls[0]["options"] == {"temperature": 0}


async def test_schema_rejected_falls_back_to_json():
    service = build_service(
        results=[({}, 400), {"message": {"content": '{"match": true}'}}]
    )

    assert await service.matches(job(title="X")) is True
    assert service.session.calls[0]["format"] == MATCH_SCHEMA
    assert service.session.calls[1]["format"] == "json"


async def test_structured_output_disabled_uses_json():
    service = OllamaAIService(
        preferences={},
        session=FakeAISession([{"message": {"content": '{"match": true}'}}]),
        structured_output=False,
    )

    assert await service.matches(job(title="X")) is True
    assert service.session.calls[0]["format"] == "json"


async def test_filter_jobs_drops_invalid_json_when_exclude():
    service = build_service(
        results=[{"message": {"content": '{"garbage": 1}'}}],
        max_attempts=1,
        fallback="exclude",
    )
    jobs = {"job-one": job(title="Anything")}

    assert await service.filter_jobs(jobs) == {}


async def test_filter_jobs_drops_non_json_content_when_exclude():
    service = build_service(
        results=[{"message": {"content": "not json"}}],
        max_attempts=1,
        fallback="exclude",
    )
    jobs = {"job-one": job(title="Anything")}

    assert await service.filter_jobs(jobs) == {}


async def test_matches_false_when_no_match_key_and_exclude():
    service = build_service(
        results=[{"message": {"content": '{"other": 1}'}}],
        max_attempts=1,
        fallback="exclude",
    )
    assert await service.matches(job(title="Anything")) is False


async def test_filter_jobs_no_matches_returns_empty():
    service = build_service(results=[])
    assert await service.filter_jobs({}) == {}


async def test_retries_ambiguous_response_until_match():
    service = build_service(
        results=[
            {"message": {"content": "garbage"}},
            {"message": {"content": '{"match": true}'}},
        ]
    )

    assert await service.matches(job(title="Python Dev")) is True
    assert len(service.session.calls) == 2


async def test_prose_wrapped_json_is_parsed():
    service = build_service(
        results=[{"message": {"content": 'Here you go: {"match": true}'}}]
    )

    assert await service.matches(job(title="X")) is True
    assert len(service.session.calls) == 1


async def test_bare_boolean_content():
    service = build_service(results=[{"message": {"content": "true"}}])

    assert await service.matches(job(title="X")) is True


async def test_double_encoded_content():
    service = build_service(results=[{"message": {"content": '"{\\"match\\": true}"'}}])

    assert await service.matches(job(title="X")) is True


async def test_wrong_key_fallback_include_after_exhaustion():
    service = build_service(
        results=[
            {"message": {"content": '{"other": 1}'}},
            {"message": {"content": '{"other": 1}'}},
            {"message": {"content": '{"other": 1}'}},
        ],
        max_attempts=3,
        fallback="include",
    )

    assert await service.matches(job(title="X")) is True
    assert len(service.session.calls) == 3


async def test_transport_error_retried_then_match():
    service = build_service(
        results=[({}, 500), {"message": {"content": '{"match": true}'}}]
    )

    assert await service.matches(job(title="X")) is True
    assert len(service.session.calls) == 2


async def test_all_transport_failures_excluded_even_with_include():
    service = build_service(
        results=[({}, 500), ({}, 500), ({}, 500)],
        max_attempts=3,
        fallback="include",
    )

    assert await service.matches(job(title="X")) is False
    assert len(service.session.calls) == 3


async def test_filter_jobs_counts_fallback_inclusions():
    service = build_service(
        results=[
            {"message": {"content": '{"other": 1}'}},
            {"message": {"content": '{"other": 1}'}},
            {"message": {"content": '{"other": 1}'}},
            {"message": {"content": '{"match": true}'}},
        ],
        preferences={"skills": ["Python"]},
    )
    jobs = {"unknown": job(title="Mystery"), "match": job(title="Python Dev")}

    matches = await service.filter_jobs(jobs)

    assert set(matches) == {"unknown", "match"}
    assert service.stats["fallback_included"] == 1
    assert service.stats["retried"] == 3


async def test_prefilter_rejects_excluded_required_skill():
    service = build_service(
        results=[],
        preferences={"excluded_skills": ["Java"]},
    )
    jj = job(title="Java Dev", required_skills=["Java"])

    assert await service.matches(jj) is False
    assert service.session.calls == []


async def test_prefilter_keeps_excluded_nice_to_have_skill():
    service = build_service(
        results=[{"message": {"content": '{"match": true}'}}],
        preferences={"excluded_skills": ["Java"]},
    )
    jj = job(
        title="Python Dev",
        required_skills=["Python"],
        nice_to_have_skills=["Java"],
    )

    assert await service.matches(jj) is True
    assert len(service.session.calls) == 1


async def test_prefilter_exact_name_match_java_not_javascript():
    service = build_service(
        results=[{"message": {"content": '{"match": true}'}}],
        preferences={"excluded_skills": ["Java"]},
    )
    jj = job(title="JS Dev", required_skills=["JavaScript"])

    assert await service.matches(jj) is True
    assert len(service.session.calls) == 1


async def test_prefilter_no_excluded_skills_skips_check():
    service = build_service(
        results=[{"message": {"content": '{"match": true}'}}],
        preferences={},
    )
    jj = job(title="Java Dev", required_skills=["Java"])

    assert await service.matches(jj) is True
    assert len(service.session.calls) == 1


def test_prompt_contains_preferences_and_raw_payload():
    service = build_service(
        results=[{"message": {"content": '{"match": true}'}}],
        preferences={"skills": ["Python"]},
    )
    jj = job(title="Python Dev", required_skills=["Python"], raw={"custom": 1})

    prompt = service._build_prompt(jj)

    assert '"skills": ["Python"]' in prompt
    assert '"required_skills": ["Python"]' in prompt
    assert '"custom": 1' in prompt
