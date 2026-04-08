from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from api.deps import get_db, make_response, require_permission, require_user
from api.helpers import fragment_category_row, fragment_content_row
from models import BizFragmentCategory, BizFragmentContent
from schemas.business import (
    FragmentCategoryAddBody,
    FragmentCategoryDeleteBody,
    FragmentCategoryEditBody,
    FragmentCategoryListBody,
    FragmentContentAddBody,
    FragmentContentChangeStatusBody,
    FragmentContentDeleteBody,
    FragmentContentEditBody,
    FragmentContentListBody,
)

router = APIRouter(prefix="/biz", tags=["业务-碎片"])


@router.post("/fragment/category/list")
def fragment_category_list(
    body: FragmentCategoryListBody,
    db: Session = Depends(get_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    q = db.query(BizFragmentCategory)
    if body.code and body.code.strip():
        q = q.filter(BizFragmentCategory.code.like(f"%{body.code.strip()}%"))
    if body.name and body.name.strip():
        q = q.filter(BizFragmentCategory.name.like(f"%{body.name.strip()}%"))

    total = q.count()
    rows = (
        q.order_by(BizFragmentCategory.id.asc())
        .offset((body.pageNum - 1) * body.pageSize)
        .limit(body.pageSize)
        .all()
    )
    return make_response(
        200,
        data={
            "list": [fragment_category_row(r) for r in rows],
            "pageNum": body.pageNum,
            "pageSize": body.pageSize,
            "total": total,
        },
        msg="success",
    )


@router.post("/fragment/category/add", dependencies=[Depends(require_permission("fragmentCategory:add"))])
def fragment_category_add(
    body: FragmentCategoryAddBody,
    db: Session = Depends(get_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    code = body.code.strip()
    name = body.name.strip()
    if not code or not name:
        return make_response(500, data={}, msg="标识码与位置名称不能为空")
    if db.query(BizFragmentCategory).filter(BizFragmentCategory.code == code).first():
        return make_response(500, data={}, msg="标识码已存在")

    db.add(BizFragmentCategory(code=code, name=name, remark=body.remark))
    db.commit()
    return make_response(200, data={}, msg="新增成功")


@router.post("/fragment/category/edit", dependencies=[Depends(require_permission("fragmentCategory:edit"))])
def fragment_category_edit(
    body: FragmentCategoryEditBody,
    db: Session = Depends(get_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    cid = int(body.id) if not isinstance(body.id, int) else body.id
    row = db.query(BizFragmentCategory).filter(BizFragmentCategory.id == cid).first()
    if not row:
        return make_response(500, data={}, msg="位置不存在")

    code = body.code.strip()
    name = body.name.strip()
    if not code or not name:
        return make_response(500, data={}, msg="标识码与位置名称不能为空")
    other = (
        db.query(BizFragmentCategory)
        .filter(BizFragmentCategory.code == code, BizFragmentCategory.id != cid)
        .first()
    )
    if other:
        return make_response(500, data={}, msg="标识码已存在")

    row.code = code
    row.name = name
    row.remark = body.remark
    db.commit()
    return make_response(200, data={}, msg="编辑成功")


@router.post("/fragment/category/delete", dependencies=[Depends(require_permission("fragmentCategory:delete"))])
def fragment_category_delete(
    body: FragmentCategoryDeleteBody,
    db: Session = Depends(get_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    deleted = 0
    for raw in body.id:
        cid = int(raw) if not isinstance(raw, int) else raw
        row = db.query(BizFragmentCategory).filter(BizFragmentCategory.id == cid).first()
        if row:
            db.query(BizFragmentContent).filter(BizFragmentContent.category_id == cid).delete(synchronize_session=False)
            db.delete(row)
            deleted += 1
    if not deleted:
        return make_response(500, data={}, msg="位置不存在或已删除")

    db.commit()
    return make_response(200, data={}, msg="删除成功")


@router.post("/fragment/content/list")
def fragment_content_list(
    body: FragmentContentListBody,
    db: Session = Depends(get_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    q = db.query(BizFragmentContent)
    if body.categoryId is not None and str(body.categoryId).strip() != "":
        cat_id = int(body.categoryId) if not isinstance(body.categoryId, int) else body.categoryId
        q = q.filter(BizFragmentContent.category_id == cat_id)
    if body.title and body.title.strip():
        q = q.filter(BizFragmentContent.title.like(f"%{body.title.strip()}%"))

    total = q.count()
    rows = (
        q.order_by(BizFragmentContent.sort.asc(), BizFragmentContent.id.desc())
        .offset((body.pageNum - 1) * body.pageSize)
        .limit(body.pageSize)
        .all()
    )
    return make_response(
        200,
        data={
            "list": [fragment_content_row(r) for r in rows],
            "pageNum": body.pageNum,
            "pageSize": body.pageSize,
            "total": total,
        },
        msg="success",
    )


@router.post("/fragment/content/add", dependencies=[Depends(require_permission("fragmentContent:add"))])
def fragment_content_add(
    body: FragmentContentAddBody,
    db: Session = Depends(get_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    if body.status not in (0, 1):
        return make_response(500, data={}, msg="状态参数无效")
    cat_id = int(body.categoryId) if not isinstance(body.categoryId, int) else body.categoryId
    if not db.query(BizFragmentCategory).filter(BizFragmentCategory.id == cat_id).first():
        return make_response(500, data={}, msg="碎片位置不存在")

    title = body.title.strip()
    if not title:
        return make_response(500, data={}, msg="标题不能为空")

    db.add(
        BizFragmentContent(
            category_id=cat_id,
            title=title,
            image_url=(body.imageUrl or "").strip() or None,
            link_url=(body.linkUrl or "").strip() or None,
            content=body.content,
            sort=body.sort,
            status=body.status,
        )
    )
    db.commit()
    return make_response(200, data={}, msg="新增成功")


@router.post("/fragment/content/edit", dependencies=[Depends(require_permission("fragmentContent:edit"))])
def fragment_content_edit(
    body: FragmentContentEditBody,
    db: Session = Depends(get_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    if body.status not in (0, 1):
        return make_response(500, data={}, msg="状态参数无效")
    rid = int(body.id) if not isinstance(body.id, int) else body.id
    row = db.query(BizFragmentContent).filter(BizFragmentContent.id == rid).first()
    if not row:
        return make_response(500, data={}, msg="内容不存在")

    title = body.title.strip()
    if not title:
        return make_response(500, data={}, msg="标题不能为空")

    row.title = title
    row.image_url = (body.imageUrl or "").strip() or None
    row.link_url = (body.linkUrl or "").strip() or None
    row.content = body.content
    row.sort = body.sort
    row.status = body.status
    db.commit()
    return make_response(200, data={}, msg="编辑成功")


@router.post("/fragment/content/delete", dependencies=[Depends(require_permission("fragmentContent:delete"))])
def fragment_content_delete(
    body: FragmentContentDeleteBody,
    db: Session = Depends(get_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    deleted = 0
    for raw in body.id:
        rid = int(raw) if not isinstance(raw, int) else raw
        r = db.query(BizFragmentContent).filter(BizFragmentContent.id == rid).first()
        if r:
            db.delete(r)
            deleted += 1
    if not deleted:
        return make_response(500, data={}, msg="内容不存在或已删除")

    db.commit()
    return make_response(200, data={}, msg="删除成功")


@router.post("/fragment/content/changeStatus", dependencies=[Depends(require_permission("fragmentContent:edit"))])
def fragment_content_change_status(
    body: FragmentContentChangeStatusBody,
    db: Session = Depends(get_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    if body.status not in (0, 1):
        return make_response(500, data={}, msg="状态参数无效")
    rid = int(body.id) if not isinstance(body.id, int) else body.id
    row = db.query(BizFragmentContent).filter(BizFragmentContent.id == rid).first()
    if not row:
        return make_response(500, data={}, msg="内容不存在")

    row.status = body.status
    db.commit()
    return make_response(200, data={}, msg="状态修改成功")
