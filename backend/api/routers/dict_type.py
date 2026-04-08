from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_async_db, invalidate_dict_cache, make_response, require_permission, require_user
from api.helpers import dict_type_row
from models import SysDictData, SysDictType
from schemas.dict import (
    DictTypeAddBody,
    DictTypeChangeStatusBody,
    DictTypeDeleteBody,
    DictTypeEditBody,
    DictTypeListBody,
)

router = APIRouter(prefix="/dict/type", tags=["字典类型"])


@router.post("/list")
async def dict_type_list(
    body: DictTypeListBody,
    db: AsyncSession = Depends(get_async_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = await require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    q = select(SysDictType).where(SysDictType.is_delete == 0)
    if body.dictName and body.dictName.strip():
        kw = f"%{body.dictName.strip()}%"
        q = q.where(SysDictType.dict_name.like(kw))
    if body.dictCode and body.dictCode.strip():
        kw = f"%{body.dictCode.strip()}%"
        q = q.where(SysDictType.dict_code.like(kw))

    rows_all = (await db.scalars(q)).all()
    total = len(rows_all)
    rows = (
        await db.scalars(
            q.order_by(SysDictType.id.desc())
            .offset((body.pageNum - 1) * body.pageSize)
            .limit(body.pageSize)
        )
    )
    rows = rows.all()
    return make_response(
        200,
        data={
            "list": [dict_type_row(r) for r in rows],
            "pageNum": body.pageNum,
            "pageSize": body.pageSize,
            "total": total,
        },
        msg="success",
    )


@router.post("/add", dependencies=[Depends(require_permission("dictType:add"))])
async def dict_type_add(
    body: DictTypeAddBody,
    db: AsyncSession = Depends(get_async_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = await require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    dict_name = body.dictName.strip()
    dict_code = body.dictCode.strip()
    if (
        await db.scalars(select(SysDictType).where(SysDictType.dict_code == dict_code, SysDictType.is_delete == 0))
    ).first():
        return make_response(500, data={}, msg="字典编码已存在")

    db.add(
        SysDictType(
            dict_name=dict_name,
            dict_code=dict_code,
            status=bool(body.status),
            remark=body.remark,
        )
    )
    await db.commit()
    return make_response(200, data={}, msg="新增成功")


@router.post("/edit", dependencies=[Depends(require_permission("dictType:edit"))])
async def dict_type_edit(
    body: DictTypeEditBody,
    db: AsyncSession = Depends(get_async_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = await require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    did = int(body.id) if not isinstance(body.id, int) else body.id
    row = (await db.scalars(select(SysDictType).where(SysDictType.id == did, SysDictType.is_delete == 0))).first()
    if not row:
        return make_response(500, data={}, msg="字典类型不存在")

    old_code = row.dict_code
    dict_name = body.dictName.strip()
    dict_code = body.dictCode.strip()
    other = (
        await db.scalars(
            select(SysDictType).where(SysDictType.dict_code == dict_code, SysDictType.id != did, SysDictType.is_delete == 0)
        )
    ).first()
    if other:
        return make_response(500, data={}, msg="字典编码已存在")

    row.dict_name = dict_name
    row.dict_code = dict_code
    row.status = bool(body.status)
    row.remark = body.remark
    await db.commit()
    invalidate_dict_cache(old_code)
    if dict_code != old_code:
        invalidate_dict_cache(dict_code)
    return make_response(200, data={}, msg="编辑成功")


@router.post("/delete", dependencies=[Depends(require_permission("dictType:delete"))])
async def dict_type_delete(
    body: DictTypeDeleteBody,
    db: AsyncSession = Depends(get_async_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = await require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    deleted = 0
    for raw in body.id:
        did = int(raw) if not isinstance(raw, int) else raw
        row = (await db.scalars(select(SysDictType).where(SysDictType.id == did, SysDictType.is_delete == 0))).first()
        if not row:
            continue
        invalidate_dict_cache(row.dict_code)
        dict_data_rows = (
            await db.scalars(select(SysDictData).where(SysDictData.dict_code == row.dict_code, SysDictData.is_delete == 0))
        ).all()
        for data_row in dict_data_rows:
            data_row.is_delete = 1
            data_row.delete_time = datetime.now()
        row.is_delete = 1
        row.delete_time = datetime.now()
        deleted += 1
    if not deleted:
        return make_response(500, data={}, msg="字典类型不存在或已删除")

    await db.commit()
    return make_response(200, data={}, msg="删除成功")


@router.post("/changeStatus", dependencies=[Depends(require_permission("dictType:edit"))])
async def dict_type_change_status(
    body: DictTypeChangeStatusBody,
    db: AsyncSession = Depends(get_async_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = await require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    did = int(body.id) if not isinstance(body.id, int) else body.id
    row = (await db.scalars(select(SysDictType).where(SysDictType.id == did, SysDictType.is_delete == 0))).first()
    if not row:
        return make_response(500, data={}, msg="字典类型不存在")

    row.status = bool(body.status)
    await db.commit()
    invalidate_dict_cache(row.dict_code)
    return make_response(200, data={}, msg="状态修改成功")
