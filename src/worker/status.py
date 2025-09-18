"""Redis-backed repository status tracking utilities."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, List

import redis

logger = logging.getLogger("snippet_extractor")

STATUS_PENDING = "pending"
STATUS_PROCESSING = "processing"
STATUS_DONE = "done"
STATUS_FAILED = "failed"


@dataclass(slots=True)
class RepoRecord:
    """State snapshot for a repository ingestion job."""

    id: str
    url: str
    status: str
    repo_name: str | None = None
    process_message: str | None = None
    fail_reason: str | None = None
    progress: int | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def repo_url(self) -> str:
        return self.url

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "url": self.url,
            "status": self.status,
            "repo_name": self.repo_name,
            "process_message": self.process_message,
            "fail_reason": self.fail_reason,
            "progress": self.progress,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RepoRecord":
        created_at = cls._parse_datetime(data.get("created_at"))
        updated_at = cls._parse_datetime(data.get("updated_at"))
        return cls(
            id=str(data["id"]),
            url=str(data["url"]),
            status=str(data.get("status", STATUS_PENDING)),
            repo_name=data.get("repo_name"),
            process_message=data.get("process_message"),
            fail_reason=data.get("fail_reason"),
            progress=_coerce_progress(data.get("progress")),
            created_at=created_at,
            updated_at=updated_at,
        )

    @staticmethod
    def _parse_datetime(value: Any) -> datetime:
        if isinstance(value, datetime):
            return value.astimezone(timezone.utc)
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value).astimezone(timezone.utc)
            except ValueError:
                pass
        return datetime.now(timezone.utc)


class RepoStatusStore:
    """Store and retrieve ingestion job state from Redis."""

    INDEX_KEY = "repos:index"
    KEY_PREFIX = "repo:record:"

    def __init__(self, redis_client: redis.Redis, *, ttl_seconds: int | None = None) -> None:
        self.redis = redis_client
        self.ttl_seconds = ttl_seconds

    def create_pending(self, repo_id: str, repo_url: str, *, repo_name: str | None = None) -> RepoRecord:
        record = RepoRecord(
            id=repo_id,
            url=repo_url,
            status=STATUS_PENDING,
            repo_name=repo_name,
            progress=0,
        )
        self._write_record(record, is_new=True)
        return record

    def get(self, repo_id: str) -> RepoRecord | None:
        raw = self.redis.get(self._record_key(repo_id))
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        try:
            data = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            return None
        try:
            return RepoRecord.from_dict(data)
        except KeyError:
            return None

    def ensure_record(
        self,
        repo_id: str,
        repo_url: str,
        *,
        repo_name: str | None = None,
    ) -> RepoRecord:
        record = self.get(repo_id)
        if record is None:
            return self.create_pending(repo_id, repo_url, repo_name=repo_name)

        updated = False
        if repo_name and record.repo_name != repo_name:
            record.repo_name = repo_name
            updated = True
        if repo_url and record.url != repo_url:
            record.url = repo_url
            updated = True
        if updated:
            record.updated_at = datetime.now(timezone.utc)
            self._write_record(record)
        return record

    def list_records(self) -> List[RepoRecord]:
        ids = self.redis.zrevrange(self.INDEX_KEY, 0, -1)
        records: List[RepoRecord] = []
        for raw_id in ids:
            repo_id = raw_id.decode("utf-8") if isinstance(raw_id, bytes) else str(raw_id)
            record = self.get(repo_id)
            if record is not None:
                records.append(record)
        return records

    def mark_processing(
        self,
        repo_id: str,
        *,
        message: str | None = None,
        repo_name: str | None = None,
        progress: int | None = None,
    ) -> RepoRecord:
        record = self._require_record(repo_id)
        record.status = STATUS_PROCESSING
        if message:
            record.process_message = message
        if repo_name:
            record.repo_name = repo_name
        record.fail_reason = None
        if progress is not None:
            record.progress = max(0, min(100, progress))
        record.updated_at = datetime.now(timezone.utc)
        self._write_record(record)
        return record

    def update_progress(
        self,
        repo_id: str,
        *,
        message: str,
        progress: int | None = None,
        repo_name: str | None = None,
    ) -> RepoRecord:
        record = self._require_record(repo_id)
        record.status = STATUS_PROCESSING
        record.process_message = message
        if repo_name:
            record.repo_name = repo_name
        if progress is not None:
            clamped_progress = max(0, min(100, progress))
            record.progress = clamped_progress
            logger.info("[%s] progress updated to %d%% - %s", repo_id, clamped_progress, message)
        else:
            logger.info("[%s] progress message: %s", repo_id, message)
        record.updated_at = datetime.now(timezone.utc)
        self._write_record(record)
        return record

    def mark_completed(
        self,
        repo_id: str,
        *,
        message: str | None = None,
        repo_name: str | None = None,
    ) -> RepoRecord:
        record = self._require_record(repo_id)
        record.status = STATUS_DONE
        if message:
            record.process_message = message
        if repo_name:
            record.repo_name = repo_name
        record.fail_reason = None
        record.progress = 100
        record.updated_at = datetime.now(timezone.utc)
        self._delete_record(record.id)
        return record

    def mark_failed(self, repo_id: str, reason: str, *, message: str | None = None, repo_name: str | None = None) -> RepoRecord:
        record = self._require_record(repo_id)
        record.status = STATUS_FAILED
        record.fail_reason = reason
        if message:
            record.process_message = message
        if repo_name:
            record.repo_name = repo_name
        record.progress = None
        record.updated_at = datetime.now(timezone.utc)
        self._write_record(record)
        return record

    def _require_record(self, repo_id: str) -> RepoRecord:
        record = self.get(repo_id)
        if record is None:
            raise KeyError(f"Unknown repo id: {repo_id}")
        return record

    def _record_key(self, repo_id: str) -> str:
        return f"{self.KEY_PREFIX}{repo_id}"

    def _write_record(self, record: RepoRecord, *, is_new: bool = False) -> None:
        payload = json.dumps(record.to_dict(), separators=(",", ":"))
        key = self._record_key(record.id)
        pipe = self.redis.pipeline()
        pipe.set(key, payload)
        if self.ttl_seconds:
            pipe.expire(key, self.ttl_seconds)
        pipe.zadd(self.INDEX_KEY, {record.id: record.created_at.timestamp()})
        pipe.execute()

    def _delete_record(self, repo_id: str) -> None:
        key = self._record_key(repo_id)
        pipe = self.redis.pipeline()
        pipe.delete(key)
        pipe.zrem(self.INDEX_KEY, repo_id)
        pipe.execute()


def _coerce_progress(value: Any) -> int | None:
    if value is None:
        return None
    try:
        progress = int(value)
    except (TypeError, ValueError):
        return None
    return max(0, min(100, progress))


__all__ = [
    "RepoRecord",
    "RepoStatusStore",
    "STATUS_DONE",
    "STATUS_FAILED",
    "STATUS_PENDING",
    "STATUS_PROCESSING",
]
