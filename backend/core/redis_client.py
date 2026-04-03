"""
Redis 连接池与带降级的缓存工具：连接失败时记录 Warning 并回退到直接读库，不中断业务。
"""
from __future__ import annotations

import json
import logging
from typing import Any, Callable, Optional, TypeVar

from redis import Redis
from redis.connection import ConnectionPool
from redis.exceptions import RedisError

from core.config import get_settings

logger = logging.getLogger(__name__)

_T = TypeVar("_T")

_pool: Optional[ConnectionPool] = None
_redis_client: Optional[Redis] = None
_redis_init_failed: bool = False


def _build_client() -> Optional[Redis]:
    global _pool, _redis_client, _redis_init_failed
    if _redis_init_failed:
        return None
    if _redis_client is not None:
        return _redis_client
    try:
        settings = get_settings()
        _pool = ConnectionPool.from_url(
            settings.redis_url,
            decode_responses=True,
            max_connections=50,
        )
        _redis_client = Redis(connection_pool=_pool)
        _redis_client.ping()
        return _redis_client
    except (RedisError, OSError, TimeoutError) as e:
        _redis_init_failed = True
        _redis_client = None
        _pool = None
        logger.warning("Redis 不可用，已降级为无缓存（直连数据库）：%s", e)
        return None


def get_redis_client() -> Optional[Redis]:
    """返回 Redis 客户端；若不可用则返回 None（静默降级）。"""
    return _build_client()


def cache_get_json(key: str) -> Optional[Any]:
    r = _build_client()
    if not r:
        return None
    try:
        raw = r.get(key)
        if raw is None:
            return None
        return json.loads(raw)
    except (RedisError, json.JSONDecodeError, TypeError, ValueError) as e:
        logger.warning("Redis GET/解析失败 [%s]，将回源数据库：%s", key, e)
        return None


def cache_set_json(key: str, value: Any, ex: Optional[int] = None) -> None:
    r = _build_client()
    if not r:
        return
    try:
        payload = json.dumps(value, ensure_ascii=False)
        if ex is not None:
            r.set(key, payload, ex=ex)
        else:
            r.set(key, payload)
    except (RedisError, TypeError, ValueError) as e:
        logger.warning("Redis SET 失败 [%s]，跳过缓存：%s", key, e)


def cache_delete(key: str) -> None:
    r = _build_client()
    if not r:
        return
    try:
        r.delete(key)
    except RedisError as e:
        logger.warning("Redis DELETE 失败 [%s]：%s", key, e)


def cache_get_or_set_json(key: str, ex: Optional[int], loader: Callable[[], _T]) -> _T:
    """
    先读缓存；未命中则调用 loader()，写回缓存（ex 为 None 表示永不过期，仅依赖主动删除）。
    Redis 不可用时等价于直接执行 loader()。
    """
    cached = cache_get_json(key)
    if cached is not None:
        return cached  # type: ignore[return-value]
    value = loader()
    cache_set_json(key, value, ex=ex)
    return value


# 与任务描述一致的单例访问：等价于 get_redis_client()
redis_client = get_redis_client
