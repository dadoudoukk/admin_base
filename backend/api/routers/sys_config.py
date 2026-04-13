from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_async_db, make_response, require_user
from core.redis_client import cache_delete, cache_get_json, cache_set_json
from models.system import SysConfig
from schemas.system import SysConfigBatchUpdate

router = APIRouter(prefix="/sys_config", tags=["系统配置"])

SYS_CONFIG_CACHE_KEY = "cache:sys_config:all"
SYS_CONFIG_CACHE_TTL_SECONDS = 7 * 24 * 3600  # 7 天

# 公开接口仅返回以下键（增删键后须清理 Redis：DEL cache:sys_config:all，否则旧缓存缺新字段）
_PUBLIC_SAFE_KEYS = ("sys_app_name", "sys_logo", "sys_login_captcha")


def _config_row(r: SysConfig) -> Dict[str, Any]:
    return {
        "id": r.id,
        "configName": r.config_name,
        "configKey": r.config_key,
        "configValue": r.config_value,
        "configType": r.config_type,
        "remark": r.remark or "",
        "createTime": r.create_time.strftime("%Y-%m-%d %H:%M:%S") if r.create_time else "",
        "updateTime": r.update_time.strftime("%Y-%m-%d %H:%M:%S") if r.update_time else "",
    }


def _cache_payload_valid(obj: Any) -> bool:
    return isinstance(obj, dict) and isinstance(obj.get("list"), list) and isinstance(obj.get("map"), dict)


async def _load_list_map_from_db(db: AsyncSession) -> Tuple[List[Dict[str, Any]], Dict[str, Optional[str]]]:
    rows = (
        await db.scalars(
            select(SysConfig)
            .where(SysConfig.is_delete == 0)
            .order_by(SysConfig.id.asc())
        )
    ).all()
    row_list = [_config_row(r) for r in rows]
    value_map = {r.config_key: r.config_value for r in rows}
    return row_list, value_map


@router.get("/public")
async def sys_config_public(db: AsyncSession = Depends(get_async_db)) -> Dict[str, Any]:
    """
    免登录公开配置：仅返回白名单键，防止敏感项泄露。
    若调整 _PUBLIC_SAFE_KEYS，请手动执行 Redis：DEL cache:sys_config:all（或等 TTL 过期），否则命中旧缓存时新键不会出现在响应中。
    """
    cached = cache_get_json(SYS_CONFIG_CACHE_KEY)
    if _cache_payload_valid(cached):
        full_map: Dict[str, Any] = cached["map"]
        value_map = {k: full_map.get(k) for k in _PUBLIC_SAFE_KEYS}
        return make_response(200, data=value_map, msg="success")

    row_list, value_map = await _load_list_map_from_db(db)
    cache_set_json(SYS_CONFIG_CACHE_KEY, {"list": row_list, "map": value_map}, ex=SYS_CONFIG_CACHE_TTL_SECONDS)
    public_data: Dict[str, Optional[str]] = {k: value_map.get(k) for k in _PUBLIC_SAFE_KEYS}
    return make_response(200, data=public_data, msg="success")


@router.get("/all")
async def sys_config_all(
    db: AsyncSession = Depends(get_async_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = await require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    cached = cache_get_json(SYS_CONFIG_CACHE_KEY)
    if _cache_payload_valid(cached):
        return make_response(200, data={"list": cached["list"], "map": cached["map"]}, msg="success")

    row_list, value_map = await _load_list_map_from_db(db)
    cache_set_json(SYS_CONFIG_CACHE_KEY, {"list": row_list, "map": value_map}, ex=SYS_CONFIG_CACHE_TTL_SECONDS)
    return make_response(
        200,
        data={"list": row_list, "map": value_map},
        msg="success",
    )


@router.put("/update")
async def sys_config_batch_update(
    body: SysConfigBatchUpdate,
    db: AsyncSession = Depends(get_async_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = await require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    merged: Dict[str, Optional[str]] = {}
    for it in body.items:
        k = (it.config_key or "").strip()
        if not k:
            return make_response(500, data={}, msg="config_key 不能为空")
        merged[k] = it.config_value

    keys = list(merged.keys())
    existing = (
        await db.scalars(
            select(SysConfig).where(SysConfig.config_key.in_(keys), SysConfig.is_delete == 0)
        )
    ).all()
    by_key = {r.config_key: r for r in existing}
    missing = [k for k in keys if k not in by_key]
    if missing:
        return make_response(500, data={"missingKeys": missing}, msg="以下配置键不存在或未启用")

    now = datetime.utcnow()
    for k, v in merged.items():
        row = by_key[k]
        row.config_value = v
        row.update_time = now

    await db.commit()
    cache_delete(SYS_CONFIG_CACHE_KEY)
    out_rows = [by_key[k] for k in keys]
    return make_response(200, data={"list": [_config_row(r) for r in out_rows]}, msg="更新成功")
