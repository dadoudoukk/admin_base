from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from api.deps import get_db, invalidate_all_user_perms_caches, make_response, require_user
from api.helpers import (
    build_menu_tree,
    build_menu_tree_all,
    fetch_menu_rows_for_user,
    filter_empty_catalogs,
    menu_list_fallback,
    query_menu_tree_for_manage,
)
from models import SysMenu
from schemas.menu import MENU_TYPES, MenuAddBody, MenuDeleteBody, MenuEditBody

router = APIRouter(tags=["菜单"])


@router.get("/menu/list")
@router.get("/auth/menuList")
def menu_list(
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    ctx = require_user(x_access_token)
    if not ctx:
        return make_response(401, data=[], msg="登录过期，请重新登录")

    rows = fetch_menu_rows_for_user(db, ctx)
    rows = filter_empty_catalogs(rows)
    tree = build_menu_tree(rows)
    if not tree:
        tree = menu_list_fallback()
    return make_response(200, data=tree, msg="success")


@router.get("/menu/all_tree")
def menu_all_tree(
    db: Session = Depends(get_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = require_user(x_access_token)
    if not ctx:
        return make_response(401, data=[], msg="登录过期，请重新登录")

    rows = (
        db.query(SysMenu)
        .filter(SysMenu.is_delete == 0)
        .filter(SysMenu.status == True)  # noqa: E712
        .order_by(SysMenu.sort.asc(), SysMenu.id.asc())
        .all()
    )
    tree = build_menu_tree_all(rows)
    return make_response(200, data=tree, msg="success")


@router.get("/menu/manage_tree")
def menu_manage_tree(
    db: Session = Depends(get_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    """菜单管理页数据源：全量树（含停用）。"""
    ctx = require_user(x_access_token)
    if not ctx:
        return make_response(401, data=[], msg="登录过期，请重新登录")
    return make_response(200, data=query_menu_tree_for_manage(db), msg="success")


@router.post("/menu/add")
def menu_add(
    body: MenuAddBody,
    db: Session = Depends(get_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    mt = (body.menuType or "MENU").strip().upper()
    if mt not in MENU_TYPES:
        return make_response(500, data={}, msg="菜单类型无效")

    pid = body.parentId
    if pid is not None:
        parent = db.query(SysMenu).filter(SysMenu.id == pid, SysMenu.is_delete == 0).first()
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
    db.commit()
    invalidate_all_user_perms_caches()
    return make_response(200, data={}, msg="新增成功")


@router.post("/menu/edit")
def menu_edit(
    body: MenuEditBody,
    db: Session = Depends(get_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    mid = int(body.id) if not isinstance(body.id, int) else body.id
    m = db.query(SysMenu).filter(SysMenu.id == mid, SysMenu.is_delete == 0).first()
    if not m:
        return make_response(500, data={}, msg="菜单不存在")

    if body.parentId is not None:
        if body.parentId == mid:
            return make_response(500, data={}, msg="不能将父级设为自身")
        if body.parentId == 0:
            m.parent_id = None
        else:
            parent = db.query(SysMenu).filter(SysMenu.id == body.parentId, SysMenu.is_delete == 0).first()
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

    db.commit()
    invalidate_all_user_perms_caches()
    return make_response(200, data={}, msg="编辑成功")


@router.post("/menu/delete")
def menu_delete(
    body: MenuDeleteBody,
    db: Session = Depends(get_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    mid = int(body.id) if not isinstance(body.id, int) else body.id
    m = db.query(SysMenu).filter(SysMenu.id == mid, SysMenu.is_delete == 0).first()
    if not m:
        return make_response(500, data={}, msg="菜单不存在")

    has_child = db.query(SysMenu).filter(SysMenu.parent_id == mid, SysMenu.is_delete == 0).first()
    if has_child:
        return make_response(500, data={}, msg="请先删除子菜单")

    m.is_delete = 1
    m.delete_time = datetime.now()
    db.commit()
    invalidate_all_user_perms_caches()
    return make_response(200, data={}, msg="删除成功")
