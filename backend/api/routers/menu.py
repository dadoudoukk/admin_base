from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_async_db, invalidate_all_user_perms_caches, make_response, require_user
from api.helpers import (
    build_menu_tree,
    build_menu_tree_all,
    filter_empty_catalogs,
    menu_list_fallback,
)
from models import SysRoleMenu, SysUserRole
from models import SysMenu
from schemas.menu import MENU_TYPES, MenuAddBody, MenuDeleteBody, MenuEditBody

router = APIRouter(tags=["菜单"])


@router.get("/menu/list")
@router.get("/auth/menuList")
async def menu_list(
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    ctx = await require_user(x_access_token)
    if not ctx:
        return make_response(401, data=[], msg="登录过期，请重新登录")

    base_stmt = (
        select(SysMenu)
        .where(SysMenu.is_delete == 0, SysMenu.status == True, SysMenu.menu_type.in_(["CATALOG", "MENU"]))  # noqa: E712
        .order_by(SysMenu.sort.asc(), SysMenu.id.asc())
    )
    if ctx.get("is_superuser") or "admin" in (ctx.get("roles") or []) or ctx.get("username") == "admin":
        rows = (await db.scalars(base_stmt)).all()
    else:
        uid = int(ctx["user_id"])
        seeded_rows = (
            await db.scalars(
                base_stmt.join(SysRoleMenu, SysRoleMenu.menu_id == SysMenu.id).join(
                    SysUserRole, SysUserRole.role_id == SysRoleMenu.role_id
                ).where(SysUserRole.user_id == uid).distinct()
            )
        ).all()
        if not seeded_rows:
            rows = []
        else:
            all_rows = (await db.scalars(base_stmt)).all()
            id_to_menu = {m.id: m for m in all_rows}
            expanded: set[int] = set()

            def add_with_parents(mid: int) -> None:
                if mid in expanded or mid not in id_to_menu:
                    return
                obj = id_to_menu[mid]
                expanded.add(mid)
                if obj.parent_id:
                    add_with_parents(obj.parent_id)

            for m in seeded_rows:
                add_with_parents(m.id)
            rows = [id_to_menu[i] for i in expanded]
            rows.sort(key=lambda m: (m.sort, m.id))
    rows = filter_empty_catalogs(rows)
    tree = build_menu_tree(rows)
    if not tree:
        tree = menu_list_fallback()
    return make_response(200, data=tree, msg="success")


@router.get("/menu/all_tree")
async def menu_all_tree(
    db: AsyncSession = Depends(get_async_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = await require_user(x_access_token)
    if not ctx:
        return make_response(401, data=[], msg="登录过期，请重新登录")

    rows = (
        await db.scalars(
            select(SysMenu)
            .where(SysMenu.is_delete == 0, SysMenu.status == True)  # noqa: E712
            .order_by(SysMenu.sort.asc(), SysMenu.id.asc())
        )
    ).all()
    tree = build_menu_tree_all(rows)
    return make_response(200, data=tree, msg="success")


@router.get("/menu/manage_tree")
async def menu_manage_tree(
    db: AsyncSession = Depends(get_async_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    """菜单管理页数据源：全量树（含停用）。"""
    ctx = await require_user(x_access_token)
    if not ctx:
        return make_response(401, data=[], msg="登录过期，请重新登录")
    rows = (
        await db.scalars(
            select(SysMenu)
            .where(SysMenu.is_delete == 0)
            .order_by(SysMenu.sort.asc(), SysMenu.id.asc())
        )
    ).all()
    return make_response(200, data=build_menu_tree_all(rows), msg="success")


@router.post("/menu/add")
async def menu_add(
    body: MenuAddBody,
    db: AsyncSession = Depends(get_async_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = await require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    mt = (body.menuType or "MENU").strip().upper()
    if mt not in MENU_TYPES:
        return make_response(500, data={}, msg="菜单类型无效")

    pid = body.parentId
    if pid is not None:
        parent = (await db.scalars(select(SysMenu).where(SysMenu.id == pid, SysMenu.is_delete == 0))).first()
        if not parent:
            return make_response(500, data={}, msg="父级菜单不存在")

    name = body.name.strip()
    raw_permission = (body.permission or "").strip()
    permission = raw_permission or (name if mt == "BUTTON" else None)

    m = SysMenu(
        parent_id=pid,
        menu_type=mt,
        name=name,
        title=body.title.strip(),
        path=(body.path or "").strip() or None,
        component=(body.component or "").strip() or None,
        icon=(body.icon or "").strip() or None,
        permission=permission,
        sort=body.sort,
        remark=body.remark,
        status=True,
    )
    db.add(m)
    await db.commit()
    invalidate_all_user_perms_caches()
    return make_response(200, data={}, msg="新增成功")


@router.post("/menu/edit")
async def menu_edit(
    body: MenuEditBody,
    db: AsyncSession = Depends(get_async_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = await require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    mid = int(body.id) if not isinstance(body.id, int) else body.id
    m = (await db.scalars(select(SysMenu).where(SysMenu.id == mid, SysMenu.is_delete == 0))).first()
    if not m:
        return make_response(500, data={}, msg="菜单不存在")

    if body.parentId is not None:
        if body.parentId == mid:
            return make_response(500, data={}, msg="不能将父级设为自身")
        if body.parentId == 0:
            m.parent_id = None
        else:
            parent = (await db.scalars(select(SysMenu).where(SysMenu.id == body.parentId, SysMenu.is_delete == 0))).first()
            if not parent:
                return make_response(500, data={}, msg="父级菜单不存在")
            m.parent_id = body.parentId

    if body.menuType is not None:
        mt = body.menuType.strip().upper()
        if mt not in MENU_TYPES:
            return make_response(500, data={}, msg="菜单类型无效")
        m.menu_type = mt
    if body.name is not None:
        m.name = body.name.strip()
    if body.title is not None:
        m.title = body.title.strip()
    if body.path is not None:
        m.path = body.path.strip() or None
    if body.component is not None:
        m.component = body.component.strip() or None
    if body.icon is not None:
        m.icon = body.icon.strip() or None
    if body.permission is not None:
        m.permission = body.permission.strip() or None
    if body.sort is not None:
        m.sort = body.sort
    if body.remark is not None:
        m.remark = body.remark
    if body.status is not None:
        m.status = body.status

    if m.menu_type == "BUTTON" and not (m.permission or "").strip():
        m.permission = (m.name or "").strip() or None

    await db.commit()
    invalidate_all_user_perms_caches()
    return make_response(200, data={}, msg="编辑成功")


@router.post("/menu/delete")
async def menu_delete(
    body: MenuDeleteBody,
    db: AsyncSession = Depends(get_async_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = await require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    mid = int(body.id) if not isinstance(body.id, int) else body.id
    m = (await db.scalars(select(SysMenu).where(SysMenu.id == mid, SysMenu.is_delete == 0))).first()
    if not m:
        return make_response(500, data={}, msg="菜单不存在")

    has_child = (await db.scalars(select(SysMenu).where(SysMenu.parent_id == mid, SysMenu.is_delete == 0))).first()
    if has_child:
        return make_response(500, data={}, msg="请先删除子菜单")

    m.is_delete = 1
    m.delete_time = datetime.now()
    await db.commit()
    invalidate_all_user_perms_caches()
    return make_response(200, data={}, msg="删除成功")
