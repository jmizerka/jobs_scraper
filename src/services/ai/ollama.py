import json
import re

from aiohttp import ClientSession

from src.config import settings
from src.logger import get_logger
from src.schemas.job import JobOffer
from src.services.ai.base import AIService

logger = get_logger(__name__)

SYSTEM_PROMPT = """
You are a strict job offer matching classifier.

Your entire response MUST be exactly one valid JSON object:
{"match": true}
or
{"match": false}

Do not output:
- explanations
- reasoning
- comments
- markdown
- code fences
- additional fields
- leading or trailing text

Decision rules:

You receive:
- user preferences
- one job offer

The job offer contains structured fields:
- required_skills
- nice_to_have_skills

These structured skill fields have already been filtered against the user's excluded skills.
DO NOT use them to decide excluded-skill mismatches.

For excluded skills:
- Inspect ONLY the job description body.
- If an excluded skill is clearly required in the body, return {"match": false}.
- If an excluded skill appears only as optional, preferred, or nice-to-have in the body, it does NOT disqualify the offer.
- Match skill names case-insensitively and exactly.
- Do not treat similar names as equal (for example, "Java" does not match "JavaScript").

For all other criteria:
- Compare salary, seniority, and work mode against user preferences.
- Return true only when the job satisfies all required preferences.

Output only the JSON object.
"""

FORMAT_NUDGE = (
    "Your previous response was not in the required format. "
    'Respond with exactly one JSON object: {"match": true} or {"match": false}. '
    "No other text."
)

MATCH_SCHEMA = {
    "type": "object",
    "properties": {"match": {"type": "boolean"}},
    "required": ["match"],
}

_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


class OllamaAIService(AIService):
    def __init__(
        self,
        preferences=None,
        model=None,
        base_url=None,
        session=None,
        max_attempts=None,
        fallback=None,
        structured_output=None,
        temperature=None,
    ):
        super().__init__(preferences)
        self.model = model or settings.get("ai", "model", default="gemma4:latest")
        self.base_url = base_url or settings.get(
            "ai", "base_url", default="http://localhost:11434"
        )
        self._owns_session = session is None
        self.session = session or ClientSession()
        self.max_attempts = max_attempts or settings.get(
            "ai", "max_attempts", default=3
        )
        self.fallback = fallback or settings.get("ai", "fallback", default="include")
        self.structured_output = (
            settings.get("ai", "structured_output", default=True)
            if structured_output is None
            else structured_output
        )
        self.temperature = (
            settings.get("ai", "temperature", default=0)
            if temperature is None
            else temperature
        )
        self._schema_unsupported = False
        self.stats = {"retried": 0, "fallback_included": 0, "transport_failed": 0}

    async def close(self):
        if self._owns_session:
            await self.session.close()

    async def filter_jobs(self, jobs: dict) -> dict:
        self.stats = {"retried": 0, "fallback_included": 0, "transport_failed": 0}
        matches = await super().filter_jobs(jobs)
        logger.info(
            "AI filtering stats: evaluated=%d kept=%d retried=%d "
            "fallback_included=%d transport_failed=%d",
            len(jobs),
            len(matches),
            self.stats["retried"],
            self.stats["fallback_included"],
            self.stats["transport_failed"],
        )
        return matches

    async def matches(self, job: JobOffer) -> bool:
        if self.deterministic_filter.has_excluded_required_skill(job):
            logger.debug("Job %s excluded by deterministic filter", job.id)
            return False

        envelope_ok = False
        for attempt in range(self.max_attempts):
            try:
                result = await self._evaluate(job, attempt)
                envelope_ok = True
            except Exception:
                logger.warning(
                    "Transport error for job %s on attempt %d", job.id, attempt + 1
                )
                self.stats["transport_failed"] += 1
                continue
            if result is not None:
                return result
            logger.debug("Ambiguous AI response for job %s on attempt %d", job.id, attempt + 1)
            self.stats["retried"] += 1

        if not envelope_ok:
            logger.error(
                "AI unreachable for job %s after %d attempts; excluding",
                job.id,
                self.max_attempts,
            )
            return False

        if self.fallback == "include":
            logger.warning(
                "Including job %s as fallback: unparseable AI response after %d attempts",
                job.id,
                self.max_attempts,
            )
            self.stats["fallback_included"] += 1
            return True
        logger.warning(
            "Excluding job %s: unparseable AI response after %d attempts",
            job.id,
            self.max_attempts,
        )
        return False

    async def _evaluate(self, job: JobOffer, attempt: int) -> bool | None:
        use_schema = self.structured_output and not self._schema_unsupported
        payload = self._build_payload(job, attempt, use_schema)
        async with self.session.post(f"{self.base_url}/api/chat", json=payload) as resp:
            if resp.status == 400 and use_schema:
                self._schema_unsupported = True
                logger.warning(
                    "Ollama rejected JSON schema; falling back to format='json'"
                )
                return await self._evaluate(job, attempt)
            if resp.status != 200:
                raise ConnectionError(f"Ollama returned status {resp.status}")
            data = await resp.json()
        return self._parse_response(data)

    def _build_payload(self, job: JobOffer, attempt: int, use_schema: bool) -> dict:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": self._build_prompt(job)},
        ]
        if attempt > 0:
            messages.append({"role": "system", "content": FORMAT_NUDGE})
        payload = {
            "model": self.model,
            "messages": messages,
            "format": MATCH_SCHEMA if use_schema else "json",
            "stream": False,
        }
        if self.temperature is not None:
            payload["options"] = {"temperature": self.temperature}
        return payload

    def _parse_response(self, data) -> bool | None:
        if not isinstance(data, dict):
            return None
        message = data.get("message")
        if not isinstance(message, dict):
            return None
        content = message.get("content")
        if not isinstance(content, str):
            return None
        return self._parse_content(content)

    @staticmethod
    def _parse_content(content: str) -> bool | None:
        try:
            return OllamaAIService._extract_decision(json.loads(content))
        except json.JSONDecodeError:
            match = _JSON_OBJECT_RE.search(content)
            if not match:
                return None
            try:
                return OllamaAIService._extract_decision(json.loads(match.group(0)))
            except json.JSONDecodeError:
                return None

    @staticmethod
    def _extract_decision(parsed) -> bool | None:
        if isinstance(parsed, bool):
            return parsed
        if isinstance(parsed, str):
            try:
                return OllamaAIService._extract_decision(json.loads(parsed))
            except (json.JSONDecodeError, TypeError):
                return None
        if isinstance(parsed, dict) and isinstance(parsed.get("match"), bool):
            return parsed["match"]
        return None

    def _build_prompt(self, job: JobOffer) -> str:
        return (
            f"User preferences:\n{json.dumps(self.preferences)}\n\n"
            f"Job offer:\n{json.dumps(job.model_dump())}"
        )
