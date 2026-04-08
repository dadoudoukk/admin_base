from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from fastapi import APIRouter, Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_async_db, invalidate_dict_cache, make_response, require_permission, require_user
from api.helpers import dict_data_row
from models import SysDictData, SysDictType
from schemas.dict import (
    DictDataAddBody,
    DictDataChangeStatusBody,
    DictDataDeleteBody,
    DictDataEditBody,
    DictDataListBody,
)

router = APIRouter(prefix="/dict/data", tags=["字典数据"])


@router.get("/{dict_code}")
async def dict_data_by_code(dict_code: str, db: AsyncSession = Depends(get_async_db)) -> Dict[str, Any]:
    code = (dict_code or "").strip()
    if not code:
        return make_response(500, data=[], msg="dictCode 不能为空")

    rows = (
        await db.scalars(
            select(SysDictData)
            .where(SysDictData.dict_code == code, SysDictData.is_delete == 0, SysDictData.status == True)  # noqa: E712
            .order_by(SysDictData.sort.asc(), SysDictData.id.asc())
        )
    ).all()
    data = [dict_data_row(r) for r in rows]
    return make_response(200, data=data, msg="success")


@router.post("/list")
async def dict_data_list(
    body: DictDataListBody,
    db: AsyncSession = Depends(get_async_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = await require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    code = body.dictCode.strip()
    if not code:
        return make_response(500, data={}, msg="dictCode 不能为空")

    q = select(SysDictData).where(SysDictData.dict_code == code, SysDictData.is_delete == 0)
    if body.dictLabel and body.dictLabel.strip():
        kw = f"%{body.dictLabel.strip()}%"
        q = q.where(SysDictData.dict_label.like(kw))
    if body.dictValue and body.dictValue.strip():
        kw = f"%{body.dictValue.strip()}%"
        q = q.where(SysDictData.dict_value.like(kw))

    rows_all = (await db.scalars(q)).all()
    total = len(rows_all)
    rows = (
        await db.scalars(
            q.order_by(SysDictData.sort.asc(), SysDictData.id.asc())
            .offset((body.pageNum - 1) * body.pageSize)
            .limit(body.pageSize)
        )
    )
    rows = rows.all()
    return make_response(
        200,
        data={
            "list": [dict_data_row(r) for r in rows],
            "pageNum": body.pageNum,
            "pageSize": body.pageSize,
            "total": total,
        },
        msg="success",
    )


@router.post("/add", dependencies=[Depends(require_permission("dictData:add"))])
async def dict_data_add(
    body: DictDataAddBody,
    db: AsyncSession = Depends(get_async_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = await require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    code = body.dictCode.strip()
    if not (await db.scalars(select(SysDictType).where(SysDictType.dict_code == code, SysDictType.is_delete == 0))).first():
        return make_response(500, data={}, msg="字典类型不存在")
    if (
        await db.scalars(
            select(SysDictData).where(
                SysDictData.dict_code == code,
                SysDictData.dict_value == body.dictValue.strip(),
                SysDictData.is_delete == 0,
            )
        )
    ).first():
        return make_response(500, data={}, msg="同字典编码下字典值已存在")

    db.add(
        SysDictData(
            dict_code=code,
            dict_label=body.dictLabel.strip(),
            dict_value=body.dictValue.strip(),
            sort=body.sort,
            status=bool(body.status),
            remark=body.remark,
        )
    )
    await db.commit()
    invalidate_dict_cache(code)
    return make_response(200, data={}, msg="新增成功")


@router.post("/edit", dependencies=[Depends(require_permission("dictData:edit"))])
async def dict_data_edit(
    body: DictDataEditBody,
    db: AsyncSession = Depends(get_async_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = await require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    did = int(body.id) if not isinstance(body.id, int) else body.id
    row = (await db.scalars(select(SysDictData).where(SysDictData.id == did, SysDictData.is_delete == 0))).first()
    if not row:
        return make_response(500, data={}, msg="字典数据不存在")

    prev_code = row.dict_code
    code = body.dictCode.strip()
    if not (await db.scalars(select(SysDictType).where(SysDictType.dict_code == code, SysDictType.is_delete == 0))).first():
        return make_response(500, data={}, msg="字典类型不存在")
    other = (await db.scalars(
        select(SysDictData).where(
            SysDictData.dict_code == code,
            SysDictData.dict_value == body.dictValue.strip(),
            SysDictData.id != did,
            SysDictData.is_delete == 0,
        )
    )).first()
    if other:
        return make_response(500, data={}, msg="同字典编码下字典值已存在")

    row.dict_code = code
    row.dict_label = body.dictLabel.strip()
    row.dict_value = body.dictValue.strip()
    row.sort = body.sort
    row.status = bool(body.status)
    row.remark = body.remark
    await db.commit()
    invalidate_dict_cache(prev_code)
    if code != prev_code:
        invalidate_dict_cache(code)
    return make_response(200, data={}, msg="编辑成功")


@router.post("/delete", dependencies=[Depends(require_permission("dictData:delete"))])
async def dict_data_delete(
    body: DictDataDeleteBody,
    db: AsyncSession = Depends(get_async_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = await require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    deleted = 0
    codes_hit: Set[str] = set()
    for raw in body.id:
        did = int(raw) if not isinstance(raw, int) else raw
        row = (await db.scalars(select(SysDictData).where(SysDictData.id == did, SysDictData.is_delete == 0))).first()
        if row:
            codes_hit.add(row.dict_code)
            row.is_delete = 1
            row.delete_time = datetime.now()
            deleted += 1
    if not deleted:
        return make_response(500, data={}, msg="字典数据不存在或已删除")

    await db.commit()
    for c in codes_hit:
        invalidate_dict_cache(c)
    return make_response(200, data={}, msg="删除成功")


@router.post("/changeStatus", dependencies=[Depends(require_permission("dictData:edit"))])
async def dict_data_change_status(
    body: DictDataChangeStatusBody,
    db: AsyncSession = Depends(get_async_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = await require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    did = int(body.id) if not isinstance(body.id, int) else body.id
    row = (await db.scalars(select(SysDictData).where(SysDictData.id == did, SysDictData.is_delete == 0))).first()
    if not row:
        return make_response(500, data={}, msg="字典数据不存在")

    row.status = bool(body.status)
    await db.commit()
    invalidate_dict_cache(row.dict_code)
    return make_response(200, data={}, msg="状态修改成功")
