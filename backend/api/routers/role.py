from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.deps import (
    get_async_db,
    invalidate_all_user_perms_caches,
    make_response,
    require_permission,
    require_user,
)
from api.helpers import role_row
from models import SysDept, SysRole, SysRoleDept, SysRoleMenu, SysUserRole
from schemas.role import (
    RoleAddBody,
    RoleAssignMenuBody,
    RoleDeleteBody,
    RoleEditBody,
    RoleListBody,
    RoleMenuIdsBody,
)

router = APIRouter(prefix="/role", tags=["角色管理"])


async def _sync_role_custom_depts(db: AsyncSession, role_id: int, data_scope: int, custom_dept_ids: list[int]) -> None:
    """
    同步角色-部门关联：
    - data_scope != 5：清空关联
    - data_scope == 5：按传入列表重建关联（去重 + 仅保留存在部门）
    """
    await db.execute(delete(SysRoleDept).where(SysRoleDept.role_id == role_id))
    if int(data_scope) != 5:
        return
    unique_ids = list(dict.fromkeys(int(x) for x in (custom_dept_ids or [])))
    if not unique_ids:
        return
    dept_ids = (await db.scalars(select(SysDept.id).where(SysDept.id.in_(unique_ids), SysDept.is_delete == 0))).all()
    valid_ids = [int(x) for x in dept_ids]
    for did in valid_ids:
        db.add(SysRoleDept(role_id=role_id, dept_id=did))


async def _build_dept_tree(db: AsyncSession) -> list[dict]:
    rows = (
        await db.scalars(
            select(SysDept).where(SysDept.is_delete == 0, SysDept.status == 1).order_by(SysDept.sort.asc(), SysDept.id.asc())
        )
    ).all()
    node_map: dict[int, dict] = {
        int(d.id): {"id": int(d.id), "label": d.name, "children": []} for d in rows
    }
    roots: list[dict] = []
    for d in rows:
        pid = d.parent_id
        cur = node_map[int(d.id)]
        if pid is not None and int(pid) in node_map:
            node_map[int(pid)]["children"].append(cur)
        else:
            roots.append(cur)
    return roots


@router.post("/list")
async def role_list_page(
    body: RoleListBody,
    db: AsyncSession = Depends(get_async_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = await require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    q = select(SysRole).where(SysRole.is_delete == 0).options(selectinload(SysRole.role_dept_associations))
    if body.roleName and body.roleName.strip():
        q = q.where(SysRole.name.like(f"%{body.roleName.strip()}%"))
    if body.roleCode and body.roleCode.strip():
        q = q.where(SysRole.code.like(f"%{body.roleCode.strip()}%"))

    total = len((await db.scalars(q)).all())
    page_num = body.pageNum
    page_size = body.pageSize
    rows = (
        await db.scalars(q.order_by(SysRole.id.desc()).offset((page_num - 1) * page_size).limit(page_size))
    ).all()
    data = {
        "list": [role_row(r) for r in rows],
        "pageNum": page_num,
        "pageSize": page_size,
        "total": total,
    }
    return make_response(200, data=data, msg="success")


@router.get("/all")
async def role_all(
    db: AsyncSession = Depends(get_async_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = await require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")
    rows = (
        await db.scalars(
            select(SysRole).where(SysRole.is_active == True, SysRole.is_delete == 0).order_by(SysRole.id.asc())  # noqa: E712
        )
    ).all()
    data = [{"id": r.id, "roleName": r.name} for r in rows]
    return make_response(200, data=data, msg="success")


@router.post("/add", dependencies=[Depends(require_permission("role:add"))])
async def role_add(
    body: RoleAddBody,
    db: AsyncSession = Depends(get_async_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = await require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    code = body.roleCode.strip()
    name = body.roleName.strip()
    if (await db.scalars(select(SysRole).where(SysRole.code == code, SysRole.is_delete == 0))).first():
        return make_response(500, data={}, msg="角色标识已存在")
    if (await db.scalars(select(SysRole).where(SysRole.name == name, SysRole.is_delete == 0))).first():
        return make_response(500, data={}, msg="角色名称已存在")

    try:
        r = SysRole(
            name=name,
            code=code,
            description=body.remark,
            data_scope=int(body.data_scope),
            is_active=True,
        )
        db.add(r)
        await db.flush()
        await _sync_role_custom_depts(db, r.id, int(body.data_scope), body.custom_dept_ids)
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    invalidate_all_user_perms_caches()
    return make_response(200, data={}, msg="新增成功")


@router.post("/edit", dependencies=[Depends(require_permission("role:edit"))])
async def role_edit(
    body: RoleEditBody,
    db: AsyncSession = Depends(get_async_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = await require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    rid = int(body.id) if not isinstance(body.id, int) else body.id
    r = (
        await db.scalars(
            select(SysRole).where(SysRole.id == rid, SysRole.is_delete == 0).options(selectinload(SysRole.role_dept_associations))
        )
    ).first()
    if not r:
        return make_response(500, data={}, msg="角色不存在")

    name = body.roleName.strip()
    code = body.roleCode.strip()
    if not name or not code:
        return make_response(500, data={}, msg="角色名称或标识不能为空")

    if r.code == "admin" and code != "admin":
        return make_response(500, data={}, msg="不能修改超级管理员角色标识")

    if name != r.name:
        if (await db.scalars(select(SysRole).where(SysRole.name == name, SysRole.id != rid, SysRole.is_delete == 0))).first():
            return make_response(500, data={}, msg="角色名称已存在")
        r.name = name
    if code != r.code:
        if (await db.scalars(select(SysRole).where(SysRole.code == code, SysRole.id != rid, SysRole.is_delete == 0))).first():
            return make_response(500, data={}, msg="角色标识已存在")
        r.code = code

    if rid == 1 and int(body.data_scope) != int(r.data_scope):
        return make_response(403, data={}, msg="禁止修改超级管理员的数据权限范围")

    try:
        if body.remark is not None:
            r.description = body.remark
        r.data_scope = int(body.data_scope)
        await _sync_role_custom_depts(db, rid, int(body.data_scope), body.custom_dept_ids)
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    invalidate_all_user_perms_caches()
    return make_response(200, data={}, msg="编辑成功")


@router.post("/delete", dependencies=[Depends(require_permission("role:delete"))])
async def role_delete(
    body: RoleDeleteBody,
    db: AsyncSession = Depends(get_async_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = await require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    deleted = 0
    for raw in body.id:
        rid = int(raw) if not isinstance(raw, int) else raw
        role = (await db.scalars(select(SysRole).where(SysRole.id == rid, SysRole.is_delete == 0))).first()
        if not role:
            continue
        if role.code == "admin":
            return make_response(500, data={}, msg="不能删除超级管理员角色")
        bind_count = (
            await db.scalar(select(func.count()).select_from(SysUserRole).where(SysUserRole.role_id == rid))
        ) or 0
        if bind_count > 0:
            return make_response(500, data={}, msg=f"角色【{role.name}】下仍有关联用户，不能删除")
        role.is_delete = 1
        role.delete_time = datetime.now()
        deleted += 1

    if not deleted:
        return make_response(500, data={}, msg="角色不存在或已删除")

    await db.commit()
    invalidate_all_user_perms_caches()
    return make_response(200, data={}, msg="删除成功")


@router.post("/getMenuIds", dependencies=[Depends(require_permission("role:auth"))])
async def role_get_menu_ids(
    body: RoleMenuIdsBody,
    db: AsyncSession = Depends(get_async_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = await require_user(x_access_token)
    if not ctx:
        return make_response(401, data=[], msg="登录过期，请重新登录")

    rid = int(body.roleId) if not isinstance(body.roleId, int) else body.roleId
    role = (
        await db.scalars(
            select(SysRole).where(SysRole.id == rid, SysRole.is_delete == 0).options(selectinload(SysRole.menus))
        )
    ).first()
    if not role:
        return make_response(500, data=[], msg="角色不存在")

    ids = [m.id for m in role.menus]
    return make_response(200, data=ids, msg="success")


@router.get("/deptTree")
async def role_dept_tree(
    db: AsyncSession = Depends(get_async_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = await require_user(x_access_token)
    if not ctx:
        return make_response(401, data=[], msg="登录过期，请重新登录")
    return make_response(200, data=await _build_dept_tree(db), msg="success")


@router.post("/assignMenu", dependencies=[Depends(require_permission("role:auth"))])
async def role_assign_menu(
    body: RoleAssignMenuBody,
    db: AsyncSession = Depends(get_async_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = await require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    rid = int(body.roleId) if not isinstance(body.roleId, int) else body.roleId
    role = (await db.scalars(select(SysRole).where(SysRole.id == rid, SysRole.is_delete == 0))).first()
    if not role:
        return make_response(500, data={}, msg="角色不存在")

    unique_ids = list(dict.fromkeys(body.menuIds))

    try:
        await db.execute(delete(SysRoleMenu).where(SysRoleMenu.role_id == rid))
        for mid in unique_ids:
            db.add(SysRoleMenu(role_id=rid, menu_id=int(mid)))
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    invalidate_all_user_perms_caches()
    return make_response(200, data={}, msg="权限分配成功")
