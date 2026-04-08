import time
from typing import Any, Dict, List, Optional

import jwt
from fastapi import Depends, Header, HTTPException
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from core.config import get_settings
from core.database import SessionLocal
from core.redis_client import cache_delete, cache_delete_by_pattern, cache_get_or_set_json
from models import SysMenu, SysRoleMenu, SysUser, SysUserRole

_settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

USER_PERMS_CACHE_PREFIX = "user:perms:"


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


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


def require_user(x_access_token: Optional[str]) -> Optional[dict]:
    if not x_access_token:
        return None
    claims = decode_access_token(x_access_token)
    if not claims:
        return None
    user_id = claims.get("user_id")
    if user_id is None:
        return None

    db = SessionLocal()
    try:
        user = db.query(SysUser).filter(SysUser.id == user_id).first()
        if not user or not user.is_active:
            return None
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
    finally:
        db.close()


def fetch_button_menus_for_user(db: Session, ctx: dict) -> List[SysMenu]:
    q = (
        db.query(SysMenu)
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
    def _checker(
        x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
        db: Session = Depends(get_db),
    ) -> bool:
        ctx = require_user(x_access_token)
        if not ctx:
            raise HTTPException(status_code=401, detail="登录过期，请重新登录")
        bundle = get_user_perms_bundle(db, ctx)
        codes = set(bundle.get("codes") or [])
        if permission_code not in codes:
            raise HTTPException(status_code=403, detail="无权限访问")
        return True

    return _checker
