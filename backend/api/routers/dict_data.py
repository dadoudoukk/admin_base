from typing import Any, Dict, List, Optional, Set

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from api.deps import get_db, invalidate_dict_cache, make_response, require_permission, require_user
from api.helpers import dict_data_row
from core.redis_client import cache_get_or_set_json
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
def dict_data_by_code(dict_code: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    code = (dict_code or "").strip()
    if not code:
        return make_response(500, data=[], msg="dictCode 不能为空")

    def load() -> List[Dict[str, Any]]:
        rows = (
            db.query(SysDictData)
            .filter(SysDictData.dict_code == code)
            .filter(SysDictData.status == True)  # noqa: E712
            .order_by(SysDictData.sort.asc(), SysDictData.id.asc())
            .all()
        )
        return [dict_data_row(r) for r in rows]

    key = f"dict:data:{code}"
    data = cache_get_or_set_json(key, None, load)
    return make_response(200, data=data, msg="success")


@router.post("/list")
def dict_data_list(
    body: DictDataListBody,
    db: Session = Depends(get_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    code = body.dictCode.strip()
    if not code:
        return make_response(500, data={}, msg="dictCode 不能为空")

    q = db.query(SysDictData).filter(SysDictData.dict_code == code)
    if body.dictLabel and body.dictLabel.strip():
        kw = f"%{body.dictLabel.strip()}%"
        q = q.filter(SysDictData.dict_label.like(kw))
    if body.dictValue and body.dictValue.strip():
        kw = f"%{body.dictValue.strip()}%"
        q = q.filter(SysDictData.dict_value.like(kw))

    total = q.count()
    rows = (
        q.order_by(SysDictData.sort.asc(), SysDictData.id.asc())
        .offset((body.pageNum - 1) * body.pageSize)
        .limit(body.pageSize)
        .all()
    )
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
def dict_data_add(
    body: DictDataAddBody,
    db: Session = Depends(get_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    code = body.dictCode.strip()
    if not db.query(SysDictType).filter(SysDictType.dict_code == code).first():
        return make_response(500, data={}, msg="字典类型不存在")
    if db.query(SysDictData).filter(SysDictData.dict_code == code, SysDictData.dict_value == body.dictValue.strip()).first():
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
    db.commit()
    invalidate_dict_cache(code)
    return make_response(200, data={}, msg="新增成功")


@router.post("/edit", dependencies=[Depends(require_permission("dictData:edit"))])
def dict_data_edit(
    body: DictDataEditBody,
    db: Session = Depends(get_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    did = int(body.id) if not isinstance(body.id, int) else body.id
    row = db.query(SysDictData).filter(SysDictData.id == did).first()
    if not row:
        return make_response(500, data={}, msg="字典数据不存在")

    prev_code = row.dict_code
    code = body.dictCode.strip()
    if not db.query(SysDictType).filter(SysDictType.dict_code == code).first():
        return make_response(500, data={}, msg="字典类型不存在")
    other = (
        db.query(SysDictData)
        .filter(SysDictData.dict_code == code, SysDictData.dict_value == body.dictValue.strip(), SysDictData.id != did)
        .first()
    )
    if other:
        return make_response(500, data={}, msg="同字典编码下字典值已存在")

    row.dict_code = code
    row.dict_label = body.dictLabel.strip()
    row.dict_value = body.dictValue.strip()
    row.sort = body.sort
    row.status = bool(body.status)
    row.remark = body.remark
    db.commit()
    invalidate_dict_cache(prev_code)
    if code != prev_code:
        invalidate_dict_cache(code)
    return make_response(200, data={}, msg="编辑成功")


@router.post("/delete", dependencies=[Depends(require_permission("dictData:delete"))])
def dict_data_delete(
    body: DictDataDeleteBody,
    db: Session = Depends(get_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    deleted = 0
    codes_hit: Set[str] = set()
    for raw in body.id:
        did = int(raw) if not isinstance(raw, int) else raw
        row = db.query(SysDictData).filter(SysDictData.id == did).first()
        if row:
            codes_hit.add(row.dict_code)
            db.delete(row)
            deleted += 1
    if not deleted:
        return make_response(500, data={}, msg="字典数据不存在或已删除")

    db.commit()
    for c in codes_hit:
        invalidate_dict_cache(c)
    return make_response(200, data={}, msg="删除成功")


@router.post("/changeStatus", dependencies=[Depends(require_permission("dictData:edit"))])
def dict_data_change_status(
    body: DictDataChangeStatusBody,
    db: Session = Depends(get_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    did = int(body.id) if not isinstance(body.id, int) else body.id
    row = db.query(SysDictData).filter(SysDictData.id == did).first()
    if not row:
        return make_response(500, data={}, msg="字典数据不存在")

    row.status = bool(body.status)
    db.commit()
    invalidate_dict_cache(row.dict_code)
    return make_response(200, data={}, msg="状态修改成功")
