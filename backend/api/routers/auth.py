from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.limiter import limiter
from api.deps import (
    create_access_token,
    get_async_db,
    get_user_perms_bundle,
    make_response,
    pwd_context,
    require_user,
)
from models import SysUser
from schemas.system import LoginBody

router = APIRouter(tags=["认证"])


@router.post("/login")
@limiter.limit("5/minute")
async def login(request: Request, body: LoginBody, db: AsyncSession = Depends(get_async_db)) -> Dict[str, Any]:
    username = body.username.strip()
    user = (await db.scalars(select(SysUser).where(SysUser.username == username, SysUser.is_delete == 0))).first()
    if not user:
        return make_response(500, data={}, msg="用户名或密码错误")
    if not pwd_context.verify(body.password, user.password):
        return make_response(500, data={}, msg="用户名或密码错误")

    token = create_access_token(user.id)
    return make_response(200, data={"access_token": token}, msg="登录成功")


@router.post("/logout")
async def logout() -> Dict[str, Any]:
    return make_response(200, data={}, msg="退出成功")


@router.get("/auth/buttons")
async def auth_buttons(
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    ctx = await require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")
    bundle = await db.run_sync(lambda s: get_user_perms_bundle(s, ctx))
    return make_response(200, data=bundle.get("buttonMap") or {}, msg="success")


@router.get("/auth/buttonList")
async def auth_button_list(
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    ctx = await require_user(x_access_token)
    if not ctx:
        return make_response(401, data=[], msg="登录过期，请重新登录")
    bundle = await db.run_sync(lambda s: get_user_perms_bundle(s, ctx))
    return make_response(200, data=bundle.get("codes") or [], msg="success")
