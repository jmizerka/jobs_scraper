import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from src.config import PROJECT_ROOT, settings

LOGGER_NAME = "job_scraper"
LOG_DIR = PROJECT_ROOT / settings.get("logging", "dir", default="logs")
LOG_FILE = LOG_DIR / settings.get("logging", "file", default="job_scraper.log")
FORMAT = settings.get(
    "logging",
    "format",
    default="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
LOG_LEVEL = settings.get("logging", "level", default="INFO")
BACKUP_COUNT = settings.get("logging", "backup_count", default=7)


def _setup() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(LOGGER_NAME)
    if logger.handlers:
        return logger
    logger.setLevel(LOG_LEVEL)
    formatter = logging.Formatter(FORMAT)
    file_handler = TimedRotatingFileHandler(
        LOG_FILE, when="midnight", interval=1, backupCount=BACKUP_COUNT, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger


logger = _setup()


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"{LOGGER_NAME}.{name}")
