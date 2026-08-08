import json
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = lambda *args, **kwargs: None

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.json"
DEFAULT_ENV_PATH = PROJECT_ROOT / ".env"


class Config:
    def __init__(self, config_path=DEFAULT_CONFIG_PATH, env_path=DEFAULT_ENV_PATH):
        load_dotenv(env_path)
        self._data = self._load(config_path)

    @staticmethod
    def _load(path: Path) -> dict:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def get(self, *keys: str, default=None):
        node = self._data
        for key in keys:
            if not isinstance(node, dict) or key not in node:
                return default
            node = node[key]
        return node

    def get_env(self, key: str, default=None):
        value = os.getenv(key)
        return value if value is not None else default


settings = Config()
