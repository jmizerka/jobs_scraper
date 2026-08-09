import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from src.schemas.job import JobOffer, JobQuery


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def config_key(
    providers: list[str], query: JobQuery, preferences: str | None = None
) -> str:
    payload = json.dumps(
        {
            "providers": sorted(providers),
            "query": query.model_dump(),
            "preferences": preferences,
        },
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def offer_key(job: JobOffer) -> str | None:
    return job.url or job.id


_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    config_key TEXT PRIMARY KEY,
    providers TEXT NOT NULL,
    query_json TEXT NOT NULL,
    preferences TEXT,
    first_run_at TEXT NOT NULL,
    last_run_at TEXT NOT NULL,
    last_success_at TEXT,
    last_publication_seen_at TEXT
);

CREATE TABLE IF NOT EXISTS offers (
    config_key TEXT NOT NULL,
    url TEXT NOT NULL,
    source TEXT,
    title TEXT,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT,
    analyzed_at TEXT,
    ai_matched INTEGER DEFAULT 0,
    email_sent_at TEXT,
    PRIMARY KEY (config_key, url)
);
"""


class JobStateStore:
    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def analyzed_urls(self, config_key: str) -> set[str]:
        rows = self._conn.execute(
            "SELECT url FROM offers WHERE config_key = ? AND analyzed_at IS NOT NULL",
            (config_key,),
        )
        return {row["url"] for row in rows}

    def mark_analyzed(
        self,
        config_key: str,
        jobs: dict[str, JobOffer],
        matched_keys: set[str] | None = None,
        email_sent_at: str | None = None,
    ) -> None:
        matched_keys = matched_keys or set()
        now = utc_now()
        with self._conn:
            for slug, job in jobs.items():
                url = offer_key(job)
                if url is None:
                    continue
                matched = int(slug in matched_keys)
                self._conn.execute(
                    """
                    INSERT INTO offers (
                        config_key, url, source, title,
                        first_seen_at, last_seen_at, analyzed_at, ai_matched, email_sent_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(config_key, url) DO UPDATE SET
                        last_seen_at = excluded.last_seen_at,
                        analyzed_at = excluded.analyzed_at,
                        ai_matched = excluded.ai_matched,
                        email_sent_at = excluded.email_sent_at
                    """,
                    (
                        config_key,
                        url,
                        job.source,
                        job.title,
                        now,
                        now,
                        now,
                        matched,
                        email_sent_at if matched else None,
                    ),
                )

    def record_run(
        self,
        config_key: str,
        providers: list[str],
        query: JobQuery,
        preferences: str | None = None,
        publications: list[str | None] | None = None,
        success: bool = True,
    ) -> None:
        now = utc_now()
        last_publication = self._max_publication(publications or [])
        row = self._conn.execute(
            "SELECT first_run_at, last_publication_seen_at FROM runs WHERE config_key = ?",
            (config_key,),
        ).fetchone()
        first_run_at = row["first_run_at"] if row else now
        if row is not None and row["last_publication_seen_at"]:
            candidates = [row["last_publication_seen_at"]]
            if last_publication:
                candidates.append(last_publication)
            last_publication = max(candidates)
        providers_json = json.dumps(sorted(providers))
        query_json = query.model_dump_json()
        with self._conn:
            if row is None:
                self._conn.execute(
                    """
                    INSERT INTO runs (
                        config_key, providers, query_json, preferences,
                        first_run_at, last_run_at, last_success_at, last_publication_seen_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        config_key,
                        providers_json,
                        query_json,
                        preferences,
                        first_run_at,
                        now,
                        now if success else None,
                        last_publication,
                    ),
                )
            else:
                self._conn.execute(
                    """
                    UPDATE runs SET
                        last_run_at = ?,
                        last_success_at = COALESCE(?, last_success_at),
                        last_publication_seen_at = COALESCE(?, last_publication_seen_at)
                    WHERE config_key = ?
                    """,
                    (
                        now,
                        now if success else None,
                        last_publication,
                        config_key,
                    ),
                )

    def get_run(self, config_key: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM runs WHERE config_key = ?", (config_key,)
        ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def _max_publication(publications: list[str | None]) -> str | None:
        values = []
        for value in publications:
            if not value:
                continue
            try:
                parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            except ValueError:
                continue
            values.append(parsed)
        if not values:
            return None
        return max(values).isoformat()
