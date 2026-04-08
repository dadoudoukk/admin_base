from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from api.deps import (
    get_db,
    invalidate_all_user_perms_caches,
    make_response,
    require_permission,
    require_user,
)
from api.helpers import role_row
from models import SysRole, SysRoleMenu, SysUserRole
from schemas.role import (
    RoleAddBody,
    RoleAssignMenuBody,
    RoleDeleteBody,
    RoleEditBody,
    RoleListBody,
    RoleMenuIdsBody,
)

router = APIRouter(prefix="/role", tags=["角色管理"])


@router.post("/list")
def role_list_page(
    body: RoleListBody,
    db: Session = Depends(get_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    q = db.query(SysRole)
    if body.roleName and body.roleName.strip():
        q = q.filter(SysRole.name.like(f"%{body.roleName.strip()}%"))
    if body.roleCode and body.roleCode.strip():
        q = q.filter(SysRole.code.like(f"%{body.roleCode.strip()}%"))

    total = q.count()
    page_num = body.pageNum
    page_size = body.pageSize
    rows = (
        q.order_by(SysRole.id.desc())
        .offset((page_num - 1) * page_size)
        .limit(page_size)
        .all()
    )
    data = {
        "list": [role_row(r) for r in rows],
        "pageNum": page_num,
        "pageSize": page_size,
        "total": total,
    }
    return make_response(200, data=data, msg="success")


@router.get("/all")
def role_all(
    db: Session = Depends(get_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")
    rows = db.query(SysRole).filter(SysRole.is_active == True).order_by(SysRole.id.asc()).all()  # noqa: E712
    data = [{"id": r.id, "roleName": r.name} for r in rows]
    return make_response(200, data=data, msg="success")


@router.post("/add", dependencies=[Depends(require_permission("role:add"))])
def role_add(
    body: RoleAddBody,
    db: Session = Depends(get_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    code = body.roleCode.strip()
    name = body.roleName.strip()
    if db.query(SysRole).filter(SysRole.code == code).first():
        return make_response(500, data={}, msg="角色标识已存在")
    if db.query(SysRole).filter(SysRole.name == name).first():
        return make_response(500, data={}, msg="角色名称已存在")

    r = SysRole(
        name=name,
        code=code,
        description=body.remark,
        is_active=True,
    )
    db.add(r)
    db.commit()
    return make_response(200, data={}, msg="新增成功")


@router.post("/edit", dependencies=[Depends(require_permission("role:edit"))])
def role_edit(
    body: RoleEditBody,
    db: Session = Depends(get_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    rid = int(body.id) if not isinstance(body.id, int) else body.id
    r = db.query(SysRole).filter(SysRole.id == rid).first()
    if not r:
        return make_response(500, data={}, msg="角色不存在")

    name = body.roleName.strip()
    code = body.roleCode.strip()
    if not name or not code:
        return make_response(500, data={}, msg="角色名称或标识不能为空")

    if r.code == "admin" and code != "admin":
        return make_response(500, data={}, msg="不能修改超级管理员角色标识")

    if name != r.name:
        if db.query(SysRole).filter(SysRole.name == name, SysRole.id != rid).first():
            return make_response(500, data={}, msg="角色名称已存在")
        r.name = name
    if code != r.code:
        if db.query(SysRole).filter(SysRole.code == code, SysRole.id != rid).first():
            return make_response(500, data={}, msg="角色标识已存在")
        r.code = code

    if body.remark is not None:
        r.description = body.remark

    db.commit()
    return make_response(200, data={}, msg="编辑成功")


@router.post("/delete", dependencies=[Depends(require_permission("role:delete"))])
def role_delete(
    body: RoleDeleteBody,
    db: Session = Depends(get_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    deleted = 0
    for raw in body.id:
        rid = int(raw) if not isinstance(raw, int) else raw
        role = db.query(SysRole).filter(SysRole.id == rid).first()
        if not role:
            continue
        if role.code == "admin":
            return make_response(500, data={}, msg="不能删除超级管理员角色")
        bind_count = db.query(SysUserRole).filter(SysUserRole.role_id == rid).count()
        if bind_count > 0:
            return make_response(500, data={}, msg=f"角色【{role.name}】下仍有关联用户，不能删除")
        db.delete(role)
        deleted += 1

    if not deleted:
        return make_response(500, data={}, msg="角色不存在或已删除")

    db.commit()
    invalidate_all_user_perms_caches()
    return make_response(200, data={}, msg="删除成功")


@router.post("/getMenuIds", dependencies=[Depends(require_permission("role:auth"))])
def role_get_menu_ids(
    body: RoleMenuIdsBody,
    db: Session = Depends(get_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = require_user(x_access_token)
    if not ctx:
        return make_response(401, data=[], msg="登录过期，请重新登录")

    rid = int(body.roleId) if not isinstance(body.roleId, int) else body.roleId
    role = db.query(SysRole).filter(SysRole.id == rid).first()
    if not role:
        return make_response(500, data=[], msg="角色不存在")

    ids = [m.id for m in role.menus]
    return make_response(200, data=ids, msg="success")


@router.post("/assignMenu", dependencies=[Depends(require_permission("role:auth"))])
def role_assign_menu(
    body: RoleAssignMenuBody,
    db: Session = Depends(get_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    rid = int(body.roleId) if not isinstance(body.roleId, int) else body.roleId
    role = db.query(SysRole).filter(SysRole.id == rid).first()
    if not role:
        return make_response(500, data={}, msg="角色不存在")

    unique_ids = list(dict.fromkeys(body.menuIds))

    try:
        db.query(SysRoleMenu).filter(SysRoleMenu.role_id == rid).delete(synchronize_session=False)
        for mid in unique_ids:
            db.add(SysRoleMenu(role_id=rid, menu_id=int(mid)))
        db.commit()
    except Exception:
        db.rollback()
        raise

    invalidate_all_user_perms_caches()
    return make_response(200, data={}, msg="权限分配成功")
