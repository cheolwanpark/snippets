"""Helpers for interacting with Redis Queue (RQ)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import redis
from rq import Queue


@dataclass(slots=True)
class QueueConfig:
    """Configuration for the background worker queue."""

    redis_url: str
    queue_name: str = "repo-ingest"
    default_timeout: int = 30 * 60  # 30 minutes
    result_ttl: int | None = None


def create_redis_connection(config: QueueConfig) -> redis.Redis:
    """Instantiate a Redis client using the provided configuration."""

    return redis.Redis.from_url(config.redis_url)


def create_queue(config: QueueConfig, *, connection: redis.Redis | None = None) -> Queue:
    """Create an RQ queue backed by the given Redis connection."""

    redis_conn = connection or create_redis_connection(config)
    kwargs: dict[str, Any] = {
        "name": config.queue_name,
        "connection": redis_conn,
        "default_timeout": config.default_timeout,
    }
    if config.result_ttl is not None:
        kwargs["default_result_ttl"] = config.result_ttl

    return Queue(**kwargs)


__all__ = ["QueueConfig", "create_queue", "create_redis_connection"]
