from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_async_db, make_response, require_permission, require_user
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
async def fragment_category_list(
    body: FragmentCategoryListBody,
    db: AsyncSession = Depends(get_async_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = await require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    q = select(BizFragmentCategory).where(BizFragmentCategory.is_delete == 0)
    if body.code and body.code.strip():
        q = q.where(BizFragmentCategory.code.like(f"%{body.code.strip()}%"))
    if body.name and body.name.strip():
        q = q.where(BizFragmentCategory.name.like(f"%{body.name.strip()}%"))

    total = (await db.scalar(select(func.count()).select_from(BizFragmentCategory).where(*q._where_criteria))) or 0
    rows = (
        await db.scalars(
            q.order_by(BizFragmentCategory.id.asc())
            .offset((body.pageNum - 1) * body.pageSize)
            .limit(body.pageSize)
        )
    ).all()
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
async def fragment_category_add(
    body: FragmentCategoryAddBody,
    db: AsyncSession = Depends(get_async_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = await require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    code = body.code.strip()
    name = body.name.strip()
    if not code or not name:
        return make_response(500, data={}, msg="标识码与位置名称不能为空")
    if (await db.scalars(select(BizFragmentCategory).where(BizFragmentCategory.code == code, BizFragmentCategory.is_delete == 0))).first():
        return make_response(500, data={}, msg="标识码已存在")

    db.add(BizFragmentCategory(code=code, name=name, remark=body.remark))
    await db.commit()
    return make_response(200, data={}, msg="新增成功")


@router.post("/fragment/category/edit", dependencies=[Depends(require_permission("fragmentCategory:edit"))])
async def fragment_category_edit(
    body: FragmentCategoryEditBody,
    db: AsyncSession = Depends(get_async_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = await require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    cid = int(body.id) if not isinstance(body.id, int) else body.id
    row = (await db.scalars(select(BizFragmentCategory).where(BizFragmentCategory.id == cid, BizFragmentCategory.is_delete == 0))).first()
    if not row:
        return make_response(500, data={}, msg="位置不存在")

    code = body.code.strip()
    name = body.name.strip()
    if not code or not name:
        return make_response(500, data={}, msg="标识码与位置名称不能为空")
    other = (await db.scalars(
        select(BizFragmentCategory).where(BizFragmentCategory.code == code, BizFragmentCategory.id != cid, BizFragmentCategory.is_delete == 0)
    )).first()
    if other:
        return make_response(500, data={}, msg="标识码已存在")

    row.code = code
    row.name = name
    row.remark = body.remark
    await db.commit()
    return make_response(200, data={}, msg="编辑成功")


@router.post("/fragment/category/delete", dependencies=[Depends(require_permission("fragmentCategory:delete"))])
async def fragment_category_delete(
    body: FragmentCategoryDeleteBody,
    db: AsyncSession = Depends(get_async_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = await require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    deleted = 0
    for raw in body.id:
        cid = int(raw) if not isinstance(raw, int) else raw
        row = (await db.scalars(select(BizFragmentCategory).where(BizFragmentCategory.id == cid, BizFragmentCategory.is_delete == 0))).first()
        if row:
            related_rows = (
                await db.scalars(
                    select(BizFragmentContent).where(BizFragmentContent.category_id == cid, BizFragmentContent.is_delete == 0)
                )
            ).all()
            now = datetime.now()
            for related in related_rows:
                related.is_delete = 1
                related.delete_time = now
            row.is_delete = 1
            row.delete_time = now
            deleted += 1
    if not deleted:
        return make_response(500, data={}, msg="位置不存在或已删除")

    await db.commit()
    return make_response(200, data={}, msg="删除成功")


@router.post("/fragment/content/list")
async def fragment_content_list(
    body: FragmentContentListBody,
    db: AsyncSession = Depends(get_async_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = await require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    q = select(BizFragmentContent).where(BizFragmentContent.is_delete == 0)
    if body.categoryId is not None and str(body.categoryId).strip() != "":
        cat_id = int(body.categoryId) if not isinstance(body.categoryId, int) else body.categoryId
        q = q.where(BizFragmentContent.category_id == cat_id)
    if body.title and body.title.strip():
        q = q.where(BizFragmentContent.title.like(f"%{body.title.strip()}%"))

    total = (await db.scalar(select(func.count()).select_from(BizFragmentContent).where(*q._where_criteria))) or 0
    rows = (
        await db.scalars(
            q.order_by(BizFragmentContent.sort.asc(), BizFragmentContent.id.desc())
            .offset((body.pageNum - 1) * body.pageSize)
            .limit(body.pageSize)
        )
    ).all()
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
async def fragment_content_add(
    body: FragmentContentAddBody,
    db: AsyncSession = Depends(get_async_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = await require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    if body.status not in (0, 1):
        return make_response(500, data={}, msg="状态参数无效")
    cat_id = int(body.categoryId) if not isinstance(body.categoryId, int) else body.categoryId
    if not (await db.scalars(select(BizFragmentCategory).where(BizFragmentCategory.id == cat_id, BizFragmentCategory.is_delete == 0))).first():
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
    await db.commit()
    return make_response(200, data={}, msg="新增成功")


@router.post("/fragment/content/edit", dependencies=[Depends(require_permission("fragmentContent:edit"))])
async def fragment_content_edit(
    body: FragmentContentEditBody,
    db: AsyncSession = Depends(get_async_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = await require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    if body.status not in (0, 1):
        return make_response(500, data={}, msg="状态参数无效")
    rid = int(body.id) if not isinstance(body.id, int) else body.id
    row = (await db.scalars(select(BizFragmentContent).where(BizFragmentContent.id == rid, BizFragmentContent.is_delete == 0))).first()
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
    await db.commit()
    return make_response(200, data={}, msg="编辑成功")


@router.post("/fragment/content/delete", dependencies=[Depends(require_permission("fragmentContent:delete"))])
async def fragment_content_delete(
    body: FragmentContentDeleteBody,
    db: AsyncSession = Depends(get_async_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = await require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    deleted = 0
    for raw in body.id:
        rid = int(raw) if not isinstance(raw, int) else raw
        r = (await db.scalars(select(BizFragmentContent).where(BizFragmentContent.id == rid, BizFragmentContent.is_delete == 0))).first()
        if r:
            r.is_delete = 1
            r.delete_time = datetime.now()
            deleted += 1
    if not deleted:
        return make_response(500, data={}, msg="内容不存在或已删除")

    await db.commit()
    return make_response(200, data={}, msg="删除成功")


@router.post("/fragment/content/changeStatus", dependencies=[Depends(require_permission("fragmentContent:edit"))])
async def fragment_content_change_status(
    body: FragmentContentChangeStatusBody,
    db: AsyncSession = Depends(get_async_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = await require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    if body.status not in (0, 1):
        return make_response(500, data={}, msg="状态参数无效")
    rid = int(body.id) if not isinstance(body.id, int) else body.id
    row = (await db.scalars(select(BizFragmentContent).where(BizFragmentContent.id == rid, BizFragmentContent.is_delete == 0))).first()
    if not row:
        return make_response(500, data={}, msg="内容不存在")

    row.status = body.status
    await db.commit()
    return make_response(200, data={}, msg="状态修改成功")
