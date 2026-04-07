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
_redis_connect_info_logged: bool = False


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
            socket_timeout=1.5,
            socket_connect_timeout=1.5,
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
    global _redis_connect_info_logged
    r = _build_client()
    if r is not None and not _redis_connect_info_logged:
        _redis_connect_info_logged = True
        settings = get_settings()
        logger.info("Redis连接成功，当前地址: %s", settings.redis_url)
    return r


def cache_get_json(key: str) -> Optional[Any]:
    r = get_redis_client()
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


def cache_set_json(key: str, value: Any, ex: Optional[int] = None) -> bool:
    logger.info("正在写入缓存键: %s", key)
    r = get_redis_client()
    if not r:
        return False
    try:
        payload = json.dumps(value, ensure_ascii=False, default=list)
        if ex is not None:
            r.set(key, payload, ex=ex)
        else:
            r.set(key, payload)
        return True
    except (RedisError, TypeError, ValueError) as e:
        logger.warning("Redis SET 失败 [%s]，跳过缓存：%s", key, e)
        return False


def cache_delete(key: str) -> None:
    r = get_redis_client()
    if not r:
        return
    try:
        r.delete(key)
    except RedisError as e:
        logger.warning("Redis DELETE 失败 [%s]：%s", key, e)


def cache_delete_by_pattern(pattern: str) -> int:
    """
    按 glob 风格 match 批量删除键（SCAN + DELETE），用于 RBAC 等需整类失效的场景。
    Redis 不可用时返回 0。
    """
    r = get_redis_client()
    if not r:
        return 0
    total = 0
    batch: list[str] = []
    try:
        for key in r.scan_iter(match=pattern, count=200):
            batch.append(key)
            if len(batch) >= 500:
                total += int(r.delete(*batch))
                batch.clear()
        if batch:
            total += int(r.delete(*batch))
    except RedisError as e:
        logger.warning("Redis SCAN/DELETE pattern [%s] 失败：%s", pattern, e)
    return total


def cache_get_or_set_json(key: str, ex: Optional[int], loader: Callable[[], _T]) -> _T:
    """
    先读缓存；未命中则调用 loader()，写回缓存（ex 为 None 表示永不过期，仅依赖主动删除）。
    Redis 不可用时等价于直接执行 loader()。
    loader() 的异常不在这里捕获，交由上层（如 FastAPI 全局异常处理）处理。
    """
    try:
        cached_data = cache_get_json(key)
        if cached_data is not None:
            return cached_data  # type: ignore[return-value]
    except Exception as e:
        logger.warning("读取 Redis 缓存异常: %s", e)

    value = loader()

    try:
        if value is not None:
            cache_set_json(key, value, ex=ex)
    except Exception as e:
        logger.warning("写入 Redis 缓存异常: %s", e)

    return value


# 与任务描述一致的单例访问：等价于 get_redis_client()
redis_client = get_redis_client
