import json
from pathlib import Path

from src.schemas.job import JobOffer

DEFAULT_PREFERENCES = Path(__file__).resolve().parents[2] / "preferences.json"


class DeterministicFilter:
    def __init__(self, preferences=None):
        self.preferences = self._load_preferences(preferences)

    @staticmethod
    def _load_preferences(preferences) -> dict:
        if preferences is None:
            preferences = DEFAULT_PREFERENCES
        if isinstance(preferences, (str, Path)):
            return json.loads(Path(preferences).read_text())
        return preferences

    def has_excluded_required_skill(self, job: JobOffer) -> bool:
        excluded = {
            skill.lower() for skill in self.preferences.get("excluded_skills", [])
        }
        if not excluded:
            return False
        required = {skill.lower() for skill in job.required_skills}
        return bool(excluded & required)
