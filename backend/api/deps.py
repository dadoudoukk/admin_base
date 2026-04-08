import time
from typing import Any, Dict, List, Optional

import jwt
from fastapi import Depends, Header, HTTPException
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session, selectinload

from core.config import get_settings
from core.context import (
    ctx_allowed_dept_ids,
    ctx_data_scope,
    ctx_dept_id,
    ctx_is_superuser,
    ctx_user_id,
)
from core.database import AsyncSessionLocal
from core.redis_client import cache_delete, cache_delete_by_pattern, cache_get_or_set_json
from models import SysMenu, SysRoleMenu, SysUser, SysUserRole
from models.rbac import DataScopeEnum, SysRole
from models.system import SysDept

_settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

USER_PERMS_CACHE_PREFIX = "user:perms:"


def get_db():
    raise RuntimeError("同步 get_db 已废弃，请使用 get_async_db")


async def get_async_db():
    if AsyncSessionLocal is None:
        raise RuntimeError("AsyncSessionLocal 未初始化，请将 DATABASE_URL 配置为异步驱动连接串")
    async with AsyncSessionLocal() as db:
        yield db


def make_response(code: int, data: Any = None, msg: str = "success") -> Dict[str, Any]:
    return {"code": code, "data": data, "msg": msg}


def create_access_token(user_id: int) -> str:
    """生成 JWT：payload 包含 user_id、iat、exp（过期时间）。"""
    now = int(time.time())
    payload = {
        "user_id": user_id,
        "iat": now,
        "exp": now + _settings.access_token_expire_seconds,
    }
    return jwt.encode(payload, _settings.secret_key, algorithm=_settings.jwt_algorithm)


def decode_access_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, _settings.secret_key, algorithms=[_settings.jwt_algorithm])
    except jwt.PyJWTError:
        return None


def _user_to_ctx_dict(user: SysUser) -> Dict[str, Any]:
    role_name = ""
    role_codes: List[str] = []
    if user.roles:
        role_name = user.roles[0].name
        role_codes = [r.code for r in user.roles]
    return {
        "user_id": user.id,
        "username": user.username,
        "avatar": user.avatar,
        "roleName": role_name,
        "roles": role_codes,
        "is_superuser": user.is_superuser,
    }


async def _collect_descendant_dept_ids(db: AsyncSession, roots: set[int]) -> set[int]:
    """批量 BFS 收集多个根部门的子孙部门 ID（含根）。"""
    if not roots:
        return set()
    acc: set[int] = set(roots)
    frontier: set[int] = set(roots)
    while frontier:
        stmt = select(SysDept.id).where(SysDept.parent_id.in_(list(frontier)), SysDept.is_delete == 0)
        children = set((await db.scalars(stmt)).all())
        children -= acc
        if not children:
            break
        acc |= children
        frontier = children
    return acc


async def activate_data_permission_context(db: AsyncSession, user: SysUser) -> None:
    """
    将当前用户的数据权限写入 contextvars（预计算可见部门集合，拦截器不做 DB IO）。
    """
    ctx_user_id.set(user.id)
    ctx_dept_id.set(user.dept_id)
    ctx_is_superuser.set(bool(user.is_superuser))

    if user.is_superuser:
        ctx_data_scope.set(DataScopeEnum.ALL.value)
        ctx_allowed_dept_ids.set(None)
        return

    roles = [r for r in (user.roles or []) if r.is_active and r.is_delete == 0]
    if not roles:
        ctx_data_scope.set(DataScopeEnum.SELF_ONLY.value)
        ctx_allowed_dept_ids.set([])
        return

    scopes = {int(r.data_scope) for r in roles}
    if DataScopeEnum.ALL.value in scopes:
        ctx_data_scope.set(DataScopeEnum.ALL.value)
        ctx_allowed_dept_ids.set(None)
        return

    # 聚合允许访问的部门 ID，覆盖「本部门」「本部门及以下」「自定义部门」
    allowed_dept_ids: set[int] = set()
    dept_only_roots: set[int] = set()
    dept_tree_roots: set[int] = set()
    custom_depts: set[int] = set()

    if user.dept_id is not None:
        if DataScopeEnum.DEPT_ONLY.value in scopes:
            dept_only_roots.add(user.dept_id)
        if DataScopeEnum.DEPT_AND_CHILD.value in scopes:
            dept_tree_roots.add(user.dept_id)

    if DataScopeEnum.CUSTOM_DEPTS.value in scopes:
        for r in roles:
            if int(r.data_scope) != DataScopeEnum.CUSTOM_DEPTS.value:
                continue
            for assoc in r.role_dept_associations:
                custom_depts.add(assoc.dept_id)

    allowed_dept_ids |= dept_only_roots
    allowed_dept_ids |= await _collect_descendant_dept_ids(db, dept_tree_roots)
    allowed_dept_ids |= custom_depts

    # SELF_ONLY 仅在没有任何部门范围时才生效
    if allowed_dept_ids:
        ctx_data_scope.set(DataScopeEnum.CUSTOM_DEPTS.value)
        ctx_allowed_dept_ids.set(list(allowed_dept_ids))
    else:
        ctx_data_scope.set(DataScopeEnum.SELF_ONLY.value)
        ctx_allowed_dept_ids.set([])


async def _load_user_by_id_for_auth(db: AsyncSession, user_id: int) -> Optional[SysUser]:
    stmt = (
        select(SysUser)
        .where(SysUser.id == user_id, SysUser.is_delete == 0)
        .options(
            selectinload(SysUser.roles).selectinload(SysRole.role_dept_associations),
        )
    )
    return (await db.scalars(stmt)).first()


async def require_user_with_data_perm(db: AsyncSession, x_access_token: Optional[str]) -> Optional[dict]:
    """解析 Token，加载用户及角色关联，写入数据权限上下文并返回与 require_user 相同结构的字典。"""
    if not x_access_token:
        return None
    claims = decode_access_token(x_access_token)
    if not claims:
        return None
    user_id = claims.get("user_id")
    if user_id is None:
        return None
    user = await _load_user_by_id_for_auth(db, int(user_id))
    if not user or not user.is_active:
        return None
    await activate_data_permission_context(db, user)
    return _user_to_ctx_dict(user)


async def require_user(x_access_token: Optional[str]) -> Optional[dict]:
    if not x_access_token:
        return None
    claims = decode_access_token(x_access_token)
    if not claims:
        return None
    user_id = claims.get("user_id")
    if user_id is None:
        return None

    if AsyncSessionLocal is None:
        return None
    async with AsyncSessionLocal() as db:
        user = await _load_user_by_id_for_auth(db, int(user_id))
        if not user or not user.is_active:
            return None
        return _user_to_ctx_dict(user)


def fetch_button_menus_for_user(db: Session, ctx: dict) -> List[SysMenu]:
    q = (
        db.query(SysMenu)
        .filter(SysMenu.is_delete == 0)
        .filter(SysMenu.status == True)  # noqa: E712
        .filter(SysMenu.menu_type == "BUTTON")
    )
    if ctx.get("is_superuser") or "admin" in (ctx.get("roles") or []) or ctx.get("username") == "admin":
        return q.order_by(SysMenu.sort.asc(), SysMenu.id.asc()).all()

    uid = int(ctx["user_id"])
    return (
        q.join(SysRoleMenu, SysRoleMenu.menu_id == SysMenu.id)
        .join(SysUserRole, SysUserRole.role_id == SysRoleMenu.role_id)
        .filter(SysUserRole.user_id == uid)
        .distinct()
        .order_by(SysMenu.sort.asc(), SysMenu.id.asc())
        .all()
    )


def _button_code(m: SysMenu) -> str:
    return (m.permission or "").strip() or (m.name or "").strip()


def _button_owner_page_name(m: SysMenu) -> str:
    cur: Optional[SysMenu] = m.parent
    while cur:
        if cur.menu_type in ("MENU", "CATALOG") and (cur.name or "").strip():
            return cur.name.strip()
        cur = cur.parent
    return "global"


def build_auth_button_map(rows: List[SysMenu]) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    for m in rows:
        code = _button_code(m)
        if not code:
            continue
        page_name = _button_owner_page_name(m)
        out.setdefault(page_name, [])
        if code not in out[page_name]:
            out[page_name].append(code)
    return out


def build_auth_button_codes(rows: List[SysMenu]) -> List[str]:
    out: List[str] = []
    for m in rows:
        code = _button_code(m)
        if code and code not in out:
            out.append(code)
    return out


def _load_user_perms_bundle(db: Session, ctx: dict) -> Dict[str, Any]:
    rows = fetch_button_menus_for_user(db, ctx)
    return {
        "codes": build_auth_button_codes(rows),
        "buttonMap": build_auth_button_map(rows),
    }


def get_user_perms_bundle(db: Session, ctx: dict) -> Dict[str, Any]:
    key = f"{USER_PERMS_CACHE_PREFIX}{ctx['user_id']}"

    def load() -> Dict[str, Any]:
        return _load_user_perms_bundle(db, ctx)

    return cache_get_or_set_json(key, 3600, load)


def invalidate_dict_cache(dict_code: Optional[str]) -> None:
    c = (dict_code or "").strip()
    if c:
        cache_delete(f"dict:data:{c}")


def invalidate_user_perms_cache(user_id: int) -> None:
    cache_delete(f"{USER_PERMS_CACHE_PREFIX}{user_id}")


def invalidate_all_user_perms_caches() -> None:
    cache_delete_by_pattern(f"{USER_PERMS_CACHE_PREFIX}*")


def require_permission(permission_code: str):
    async def _checker(
        x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
        db: AsyncSession = Depends(get_async_db),
    ) -> bool:
        ctx = await require_user(x_access_token)
        if not ctx:
            raise HTTPException(status_code=401, detail="登录过期，请重新登录")
        bundle = await db.run_sync(lambda s: get_user_perms_bundle(s, ctx))
        codes = set(bundle.get("codes") or [])
        if permission_code not in codes:
            raise HTTPException(status_code=403, detail="无权限访问")
        return True

    return _checker
