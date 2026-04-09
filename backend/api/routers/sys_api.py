from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, Request
from fastapi.routing import APIRoute
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_async_db, make_response, require_user
from core.redis_client import cache_delete_by_pattern, cache_get_json, cache_set_json, get_redis_client
from models import SysApi, SysMenu
from schemas.system import SysApiChangeStatusBody, SysApiListBody, SysApiUpdateBody

router = APIRouter(prefix="/sys/api", tags=["接口管理"])

SYS_API_CACHE_PREFIX = "sys:api:cfg:"
SYS_API_RATE_PREFIX = "sys:api:rate:"
SYS_API_EMPTY_TTL_SECONDS = 60
_EXCLUDE_ROUTE_PREFIXES = ("/docs", "/redoc", "/openapi.json", "/uploads")


def normalize_api_key(path: str, method: str) -> str:
    return f"{path}:{method.upper()}"


def build_api_cache_key(path: str, method: str) -> str:
    return f"{SYS_API_CACHE_PREFIX}{normalize_api_key(path, method)}"


def parse_api_module(path: str) -> str:
    parts = [p for p in path.split("/") if p]
    if not parts:
        return "系统"
    if parts[0] == "api" and len(parts) > 1:
        return parts[1]
    return parts[0]


async def _load_menu_api_module_rules(db: AsyncSession) -> list[tuple[str, str]]:
    """(路径前缀, 菜单标题)，按前缀长度降序，供最长匹配。"""
    rows = (
        await db.scalars(
            select(SysMenu).where(
                SysMenu.is_delete == 0,
                SysMenu.menu_type == "MENU",
            )
        )
    ).all()
    pairs: list[tuple[str, str]] = []
    for m in rows:
        raw = (m.api_path_prefix or "").strip()
        if not raw:
            continue
        title = (m.title or "").strip() or (m.name or "").strip() or "未命名"
        for part in raw.split(","):
            seg = part.strip().rstrip("/")
            if not seg:
                continue
            if not seg.startswith("/"):
                seg = "/" + seg
            pairs.append((seg, title))
    pairs.sort(key=lambda x: len(x[0]), reverse=True)
    return pairs


def _resolve_api_module_title(path: str, rules: list[tuple[str, str]]) -> str:
    p = path.rstrip("/") if path else ""
    for prefix, title in rules:
        if p == prefix or p.startswith(prefix + "/"):
            return title
    return "其他"


def _api_row(row: SysApi) -> Dict[str, Any]:
    return {
        "id": str(row.id),
        "apiPath": row.api_path,
        "apiMethod": row.api_method,
        "apiName": row.api_name or "",
        "apiModule": row.api_module or "",
        "status": 1 if row.status else 0,
        "authRequired": 1 if row.auth_required else 0,
        "logRequired": 1 if row.log_required else 0,
        "rateLimit": int(row.rate_limit or 0),
        "remark": row.remark or "",
        "createTime": row.create_time.strftime("%Y-%m-%d %H:%M:%S") if row.create_time else "",
        "updateTime": row.update_time.strftime("%Y-%m-%d %H:%M:%S") if row.update_time else "",
    }


async def refresh_api_cache(db: AsyncSession) -> None:
    cache_delete_by_pattern(f"{SYS_API_CACHE_PREFIX}*")
    rows = (
        await db.scalars(
            select(SysApi).where(SysApi.is_delete == 0).order_by(SysApi.id.asc())
        )
    ).all()
    for row in rows:
        payload = {
            "exists": True,
            "id": row.id,
            "status": bool(row.status),
            "auth_required": bool(row.auth_required),
            "log_required": bool(row.log_required),
            "rate_limit": int(row.rate_limit or 0),
        }
        cache_set_json(build_api_cache_key(row.api_path, row.api_method), payload)


async def load_api_control_config(db: AsyncSession, path: str, method: str) -> Optional[Dict[str, Any]]:
    key = build_api_cache_key(path, method)
    cached = cache_get_json(key)
    if isinstance(cached, dict):
        return cached
    row = (
        await db.scalars(
            select(SysApi).where(
                SysApi.api_path == path,
                SysApi.api_method == method.upper(),
                SysApi.is_delete == 0,
            )
        )
    ).first()
    if not row:
        # 缓存穿透保护：不存在的接口写短 TTL 空标记，避免恶意路径持续打 DB。
        cache_set_json(
            key,
            {
                "exists": False,
                "status": True,
                "auth_required": False,
                "log_required": False,
                "rate_limit": 0,
            },
            ex=SYS_API_EMPTY_TTL_SECONDS,
        )
        return None
    payload = {
        "exists": True,
        "id": row.id,
        "status": bool(row.status),
        "auth_required": bool(row.auth_required),
        "log_required": bool(row.log_required),
        "rate_limit": int(row.rate_limit or 0),
    }
    cache_set_json(key, payload)
    return payload


def check_api_rate_limit(path: str, method: str, qps: int) -> bool:
    if qps <= 0:
        return True
    r = get_redis_client()
    if r is None:
        return True
    now = int(time.time())
    key = f"{SYS_API_RATE_PREFIX}{normalize_api_key(path, method)}:{now}"
    try:
        value = r.incr(key)
        if value == 1:
            r.expire(key, 2)
        return int(value) <= int(qps)
    except Exception:
        return True


def _is_business_route(route: APIRoute) -> bool:
    if any(route.path.startswith(p) for p in _EXCLUDE_ROUTE_PREFIXES):
        return False
    if route.path.startswith("/api/health"):
        return False
    return True


@router.post("/sync")
async def sync_sys_api(
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = await require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    module_rules = await _load_menu_api_module_rules(db)

    discovered: Dict[str, Dict[str, str]] = {}
    for route in request.app.routes:
        if not isinstance(route, APIRoute):
            continue
        if not _is_business_route(route):
            continue
        methods = [m for m in (route.methods or []) if m not in ("HEAD", "OPTIONS")]
        for method in methods:
            method_upper = method.upper()
            route_key = normalize_api_key(route.path, method_upper)
            if route_key in discovered:
                continue
            discovered[route_key] = {
                "path": route.path,
                "method": method_upper,
                "name": (route.summary or route.name or "").strip(),
                "module": _resolve_api_module_title(route.path, module_rules),
            }

    existing_rows = (
        await db.scalars(select(SysApi).where(SysApi.is_delete == 0))
    ).all()
    existing_map = {normalize_api_key(r.api_path, r.api_method): r for r in existing_rows}

    created = 0
    disabled = 0
    updated_name = 0
    now = datetime.utcnow()

    for route_key, item in discovered.items():
        row = existing_map.get(route_key)
        if row is None:
            db.add(
                SysApi(
                    api_path=item["path"],
                    api_method=item["method"],
                    api_name=item["name"] or item["path"],
                    api_module=item["module"],
                    status=True,
                    auth_required=True,
                    log_required=False,
                    rate_limit=0,
                )
            )
            created += 1
            continue
        if item["name"] and row.api_name != item["name"]:
            row.api_name = item["name"]
            updated_name += 1
        row.api_module = item["module"]
        row.update_time = now

    discovered_keys = set(discovered.keys())
    for row in existing_rows:
        row_key = normalize_api_key(row.api_path, row.api_method)
        if row_key in discovered_keys:
            continue
        if row.status:
            row.status = False
            disabled += 1
        row.update_time = now
        if not (row.remark or "").strip():
            row.remark = "自动同步标记：路由不存在，已停用"

    await db.commit()
    await refresh_api_cache(db)
    return make_response(
        200,
        data={
            "created": created,
            "disabled": disabled,
            "updatedName": updated_name,
            "totalDiscovered": len(discovered),
        },
        msg="同步完成",
    )


@router.get("/module_options")
async def sys_api_module_options(
    db: AsyncSession = Depends(get_async_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    """所属模块下拉：已配置 api_path_prefix 的菜单标题 +「其他」。"""
    ctx = await require_user(x_access_token)
    if not ctx:
        return make_response(401, data=[], msg="登录过期，请重新登录")

    rows = (
        await db.scalars(
            select(SysMenu).where(SysMenu.is_delete == 0, SysMenu.menu_type == "MENU")
        )
    ).all()
    titles: set[str] = set()
    for m in rows:
        if (m.api_path_prefix or "").strip():
            t = (m.title or "").strip()
            if t:
                titles.add(t)
    ordered = sorted(titles)
    options = [{"label": t, "value": t} for t in ordered]
    options.append({"label": "其他", "value": "其他"})
    return make_response(200, data=options, msg="success")


@router.post("/list")
async def sys_api_list(
    body: SysApiListBody,
    db: AsyncSession = Depends(get_async_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = await require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    q = select(SysApi).where(SysApi.is_delete == 0)
    if body.apiPath and body.apiPath.strip():
        q = q.where(SysApi.api_path.like(f"%{body.apiPath.strip()}%"))
    if body.apiMethod and body.apiMethod.strip():
        q = q.where(SysApi.api_method == body.apiMethod.strip().upper())
    if body.apiModule and body.apiModule.strip():
        q = q.where(SysApi.api_module.like(f"%{body.apiModule.strip()}%"))

    rows_all = (await db.scalars(q)).all()
    rows = (
        await db.scalars(
            q.order_by(SysApi.id.desc())
            .offset((body.pageNum - 1) * body.pageSize)
            .limit(body.pageSize)
        )
    ).all()
    return make_response(
        200,
        data={
            "list": [_api_row(r) for r in rows],
            "pageNum": body.pageNum,
            "pageSize": body.pageSize,
            "total": len(rows_all),
        },
        msg="success",
    )


@router.post("/edit")
async def sys_api_edit(
    body: SysApiUpdateBody,
    db: AsyncSession = Depends(get_async_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = await require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    sid = int(body.id) if not isinstance(body.id, int) else body.id
    row = (await db.scalars(select(SysApi).where(SysApi.id == sid, SysApi.is_delete == 0))).first()
    if not row:
        return make_response(500, data={}, msg="接口配置不存在")

    if body.api_name is not None:
        row.api_name = body.api_name.strip()
    if body.api_module is not None:
        row.api_module = body.api_module.strip()
    if body.status is not None:
        row.status = bool(body.status)
    if body.auth_required is not None:
        row.auth_required = bool(body.auth_required)
    if body.log_required is not None:
        row.log_required = bool(body.log_required)
    if body.rate_limit is not None:
        row.rate_limit = max(0, int(body.rate_limit))
    if body.remark is not None:
        row.remark = body.remark.strip()
    row.update_time = datetime.utcnow()

    await db.commit()
    await refresh_api_cache(db)
    return make_response(200, data={}, msg="修改成功")


@router.post("/changeStatus")
async def sys_api_change_status(
    body: SysApiChangeStatusBody,
    db: AsyncSession = Depends(get_async_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = await require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    sid = int(body.id) if not isinstance(body.id, int) else body.id
    row = (await db.scalars(select(SysApi).where(SysApi.id == sid, SysApi.is_delete == 0))).first()
    if not row:
        return make_response(500, data={}, msg="接口配置不存在")

    field = (body.field or "").strip()
    value = bool(int(body.value)) if isinstance(body.value, int) else bool(body.value)
    if field not in ("status", "auth_required", "log_required"):
        return make_response(500, data={}, msg="不支持的开关字段")

    setattr(row, field, value)
    row.update_time = datetime.utcnow()
    await db.commit()
    await refresh_api_cache(db)
    return make_response(200, data={}, msg="状态修改成功")
