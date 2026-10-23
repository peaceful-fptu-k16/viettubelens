import sqlite3
import threading
import time
from pathlib import Path

from .schemas import AnalysisResult


class AnalysisCache:
    def __init__(self, path: Path, ttl_seconds: int) -> None:
        self.path = path
        self.ttl_seconds = ttl_seconds
        self._lock = threading.Lock()
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS analysis_cache (
                cache_key TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                created_at REAL NOT NULL
                )"""
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=10)

    def get(self, video_id: str, model_version: str) -> AnalysisResult | None:
        key = f"{video_id}:{model_version}"
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT payload, created_at FROM analysis_cache WHERE cache_key = ?", (key,)
            ).fetchone()
            if row is None:
                return None
            if time.time() - float(row[1]) > self.ttl_seconds:
                connection.execute("DELETE FROM analysis_cache WHERE cache_key = ?", (key,))
                return None
            result = AnalysisResult.model_validate_json(row[0])
            return result.model_copy(update={"cache_hit": True})

    def put(self, result: AnalysisResult) -> None:
        key = f"{result.video_id}:{result.model_version}"
        payload = result.model_copy(update={"cache_hit": False}).model_dump_json()
        with self._lock, self._connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO analysis_cache"
                "(cache_key, payload, created_at) VALUES (?, ?, ?)",
                (key, payload, time.time()),
            )

    def clear(self) -> int:
        with self._lock, self._connect() as connection:
            cursor = connection.execute("DELETE FROM analysis_cache")
            return max(cursor.rowcount, 0)
