from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.deps import get_db, make_response, require_permission, require_user, require_user_with_data_perm
from api.helpers import compute_home_statistics, news_article_row, news_category_row
from core.context import ctx_dept_id, ctx_user_id
from core.data_perm import apply_data_scope
from core.redis_client import cache_get_or_set_json
from models import BizNewsArticle, BizNewsCategory
from schemas.business import (
    NewsArticleAddBody,
    NewsArticleChangeStatusBody,
    NewsArticleDeleteBody,
    NewsArticleEditBody,
    NewsArticleListBody,
    NewsCategoryAddBody,
    NewsCategoryChangeStatusBody,
    NewsCategoryDeleteBody,
    NewsCategoryEditBody,
    NewsCategoryListBody,
)

router = APIRouter(prefix="/biz", tags=["业务-新闻"])


@router.get("/home/statistics")
def biz_home_statistics(
    db: Session = Depends(get_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    def load() -> Dict[str, Any]:
        return compute_home_statistics(db)

    data = cache_get_or_set_json("home:stats", 300, load)
    return make_response(200, data=data, msg="success")


@router.post("/newsCategory/list")
def news_category_list(
    body: NewsCategoryListBody,
    db: Session = Depends(get_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = require_user_with_data_perm(db, x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    stmt = select(BizNewsCategory).where(BizNewsCategory.is_delete == 0)
    if body.categoryName and body.categoryName.strip():
        stmt = stmt.where(BizNewsCategory.category_name.like(f"%{body.categoryName.strip()}%"))
    stmt = apply_data_scope(stmt, BizNewsCategory)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = int(db.scalar(count_stmt) or 0)

    stmt = stmt.order_by(BizNewsCategory.sort.asc(), BizNewsCategory.id.asc())
    stmt = stmt.offset((body.pageNum - 1) * body.pageSize).limit(body.pageSize)
    rows = list(db.scalars(stmt).all())
    return make_response(
        200,
        data={
            "list": [news_category_row(r) for r in rows],
            "pageNum": body.pageNum,
            "pageSize": body.pageSize,
            "total": total,
        },
        msg="success",
    )


@router.post("/newsCategory/add", dependencies=[Depends(require_permission("newsCategory:add"))])
def news_category_add(
    body: NewsCategoryAddBody,
    db: Session = Depends(get_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = require_user_with_data_perm(db, x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    if body.status not in (0, 1):
        return make_response(500, data={}, msg="状态参数无效")
    category_name = body.categoryName.strip()
    if not category_name:
        return make_response(500, data={}, msg="分类名称不能为空")
    dup_stmt = (
        select(BizNewsCategory.id)
        .where(BizNewsCategory.category_name == category_name, BizNewsCategory.is_delete == 0)
        .limit(1)
    )
    if db.scalars(dup_stmt).first() is not None:
        return make_response(500, data={}, msg="分类名称已存在")

    db.add(
        BizNewsCategory(
            category_name=category_name,
            sort=body.sort,
            status=body.status,
            remark=body.remark,
            dept_id=ctx_dept_id.get(),
            created_by=ctx_user_id.get(),
        )
    )
    db.commit()
    return make_response(200, data={}, msg="新增成功")


@router.post("/newsCategory/edit", dependencies=[Depends(require_permission("newsCategory:edit"))])
def news_category_edit(
    body: NewsCategoryEditBody,
    db: Session = Depends(get_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = require_user_with_data_perm(db, x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    if body.status not in (0, 1):
        return make_response(500, data={}, msg="状态参数无效")
    cid = int(body.id) if not isinstance(body.id, int) else body.id
    stmt = select(BizNewsCategory).where(BizNewsCategory.id == cid, BizNewsCategory.is_delete == 0)
    stmt = apply_data_scope(stmt, BizNewsCategory)
    row = db.scalars(stmt).first()
    if not row:
        exists = db.scalars(
            select(BizNewsCategory.id).where(BizNewsCategory.id == cid, BizNewsCategory.is_delete == 0).limit(1)
        ).first()
        if exists is not None:
            return make_response(403, data={}, msg="无权限访问该分类")
        return make_response(500, data={}, msg="分类不存在")

    category_name = body.categoryName.strip()
    if not category_name:
        return make_response(500, data={}, msg="分类名称不能为空")
    other_stmt = select(BizNewsCategory).where(
        BizNewsCategory.category_name == category_name,
        BizNewsCategory.id != cid,
        BizNewsCategory.is_delete == 0,
    )
    other = db.scalars(other_stmt).first()
    if other:
        return make_response(500, data={}, msg="分类名称已存在")

    row.category_name = category_name
    row.sort = body.sort
    row.status = body.status
    row.remark = body.remark
    db.commit()
    return make_response(200, data={}, msg="编辑成功")


@router.post("/newsCategory/delete", dependencies=[Depends(require_permission("newsCategory:delete"))])
def news_category_delete(
    body: NewsCategoryDeleteBody,
    db: Session = Depends(get_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = require_user_with_data_perm(db, x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    deleted = 0
    for raw in body.id:
        cid = int(raw) if not isinstance(raw, int) else raw
        stmt = select(BizNewsCategory).where(BizNewsCategory.id == cid, BizNewsCategory.is_delete == 0)
        stmt = apply_data_scope(stmt, BizNewsCategory)
        row = db.scalars(stmt).first()
        if row:
            row.is_delete = 1
            row.delete_time = datetime.now()
            deleted += 1
    if not deleted:
        exists_stmt = select(BizNewsCategory.id).where(
            BizNewsCategory.id.in_([int(x) if not isinstance(x, int) else x for x in body.id]),
            BizNewsCategory.is_delete == 0,
        ).limit(1)
        if db.scalars(exists_stmt).first() is not None:
            return make_response(403, data={}, msg="无权限删除所选分类")
        return make_response(500, data={}, msg="分类不存在或已删除")

    db.commit()
    return make_response(200, data={}, msg="删除成功")


@router.post("/newsCategory/changeStatus", dependencies=[Depends(require_permission("newsCategory:edit"))])
def news_category_change_status(
    body: NewsCategoryChangeStatusBody,
    db: Session = Depends(get_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = require_user_with_data_perm(db, x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    if body.status not in (0, 1):
        return make_response(500, data={}, msg="状态参数无效")
    cid = int(body.id) if not isinstance(body.id, int) else body.id
    stmt = select(BizNewsCategory).where(BizNewsCategory.id == cid, BizNewsCategory.is_delete == 0)
    stmt = apply_data_scope(stmt, BizNewsCategory)
    row = db.scalars(stmt).first()
    if not row:
        exists = db.scalars(
            select(BizNewsCategory.id).where(BizNewsCategory.id == cid, BizNewsCategory.is_delete == 0).limit(1)
        ).first()
        if exists is not None:
            return make_response(403, data={}, msg="无权限访问该分类")
        return make_response(500, data={}, msg="分类不存在")

    row.status = body.status
    db.commit()
    return make_response(200, data={}, msg="状态修改成功")


@router.get("/newsCategory/all")
def news_category_all(
    db: Session = Depends(get_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = require_user_with_data_perm(db, x_access_token)
    if not ctx:
        return make_response(401, data=[], msg="登录过期，请重新登录")

    stmt = select(BizNewsCategory).where(BizNewsCategory.status == 1, BizNewsCategory.is_delete == 0)
    stmt = apply_data_scope(stmt, BizNewsCategory)
    stmt = stmt.order_by(BizNewsCategory.sort.asc(), BizNewsCategory.id.asc())
    rows = list(db.scalars(stmt).all())
    data = [{"id": str(r.id), "categoryName": r.category_name} for r in rows]
    return make_response(200, data=data, msg="success")


@router.post("/newsArticle/list")
def news_article_list(
    body: NewsArticleListBody,
    db: Session = Depends(get_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = require_user_with_data_perm(db, x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    stmt = select(BizNewsArticle).where(BizNewsArticle.is_delete == 0)
    if body.title and body.title.strip():
        stmt = stmt.where(BizNewsArticle.title.like(f"%{body.title.strip()}%"))
    if body.categoryId is not None and str(body.categoryId).strip() != "":
        cid = int(body.categoryId) if not isinstance(body.categoryId, int) else body.categoryId
        stmt = stmt.where(BizNewsArticle.category_id == cid)
    stmt = apply_data_scope(stmt, BizNewsArticle)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = int(db.scalar(count_stmt) or 0)

    stmt = stmt.order_by(BizNewsArticle.is_top.desc(), BizNewsArticle.id.desc())
    stmt = stmt.offset((body.pageNum - 1) * body.pageSize).limit(body.pageSize)
    rows = list(db.scalars(stmt).all())

    cat_stmt = select(BizNewsCategory).where(BizNewsCategory.is_delete == 0)
    cat_stmt = apply_data_scope(cat_stmt, BizNewsCategory)
    category_map = {str(c.id): c.category_name for c in db.scalars(cat_stmt).all()}
    data_list = [news_article_row(r, category_map.get(str(r.category_id), "")) for r in rows]
    return make_response(
        200,
        data={
            "list": data_list,
            "pageNum": body.pageNum,
            "pageSize": body.pageSize,
            "total": total,
        },
        msg="success",
    )


@router.post("/newsArticle/add", dependencies=[Depends(require_permission("newsArticle:add"))])
def news_article_add(
    body: NewsArticleAddBody,
    db: Session = Depends(get_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = require_user_with_data_perm(db, x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    if body.newsType not in (0, 1) or body.isTop not in (0, 1) or body.status not in (0, 1):
        return make_response(500, data={}, msg="状态或类型参数无效")
    cid = int(body.categoryId) if not isinstance(body.categoryId, int) else body.categoryId
    cat_stmt = select(BizNewsCategory).where(BizNewsCategory.id == cid, BizNewsCategory.is_delete == 0)
    cat_stmt = apply_data_scope(cat_stmt, BizNewsCategory)
    if not db.scalars(cat_stmt).first():
        return make_response(500, data={}, msg="新闻分类不存在")

    title = body.title.strip()
    if not title:
        return make_response(500, data={}, msg="新闻标题不能为空")

    db.add(
        BizNewsArticle(
            category_id=cid,
            title=title,
            author=(body.author or "").strip() or None,
            news_type=body.newsType,
            content=body.content,
            redirect_url=(body.redirectUrl or "").strip() or None,
            cover_image_url=(body.imageUrl or "").strip() or None,
            is_top=body.isTop,
            status=body.status,
            dept_id=ctx_dept_id.get(),
            created_by=ctx_user_id.get(),
        )
    )
    db.commit()
    return make_response(200, data={}, msg="新增成功")


@router.post("/newsArticle/edit", dependencies=[Depends(require_permission("newsArticle:edit"))])
def news_article_edit(
    body: NewsArticleEditBody,
    db: Session = Depends(get_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = require_user_with_data_perm(db, x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    if body.newsType not in (0, 1) or body.isTop not in (0, 1) or body.status not in (0, 1):
        return make_response(500, data={}, msg="状态或类型参数无效")
    aid = int(body.id) if not isinstance(body.id, int) else body.id
    row_stmt = select(BizNewsArticle).where(BizNewsArticle.id == aid, BizNewsArticle.is_delete == 0)
    row_stmt = apply_data_scope(row_stmt, BizNewsArticle)
    row = db.scalars(row_stmt).first()
    if not row:
        exists = db.scalars(
            select(BizNewsArticle.id).where(BizNewsArticle.id == aid, BizNewsArticle.is_delete == 0).limit(1)
        ).first()
        if exists is not None:
            return make_response(403, data={}, msg="无权限访问该文章")
        return make_response(500, data={}, msg="文章不存在")

    cid = int(body.categoryId) if not isinstance(body.categoryId, int) else body.categoryId
    cat_stmt = select(BizNewsCategory).where(BizNewsCategory.id == cid, BizNewsCategory.is_delete == 0)
    cat_stmt = apply_data_scope(cat_stmt, BizNewsCategory)
    if not db.scalars(cat_stmt).first():
        return make_response(500, data={}, msg="新闻分类不存在")

    title = body.title.strip()
    if not title:
        return make_response(500, data={}, msg="新闻标题不能为空")

    row.category_id = cid
    row.title = title
    row.author = (body.author or "").strip() or None
    row.news_type = body.newsType
    row.content = body.content
    row.redirect_url = (body.redirectUrl or "").strip() or None
    row.cover_image_url = (body.imageUrl or "").strip() or None
    row.is_top = body.isTop
    row.status = body.status
    db.commit()
    return make_response(200, data={}, msg="编辑成功")


@router.post("/newsArticle/delete", dependencies=[Depends(require_permission("newsArticle:delete"))])
def news_article_delete(
    body: NewsArticleDeleteBody,
    db: Session = Depends(get_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = require_user_with_data_perm(db, x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    deleted = 0
    for raw in body.id:
        aid = int(raw) if not isinstance(raw, int) else raw
        stmt = select(BizNewsArticle).where(BizNewsArticle.id == aid, BizNewsArticle.is_delete == 0)
        stmt = apply_data_scope(stmt, BizNewsArticle)
        row = db.scalars(stmt).first()
        if row:
            row.is_delete = 1
            row.delete_time = datetime.now()
            deleted += 1
    if not deleted:
        exists_stmt = select(BizNewsArticle.id).where(
            BizNewsArticle.id.in_([int(x) if not isinstance(x, int) else x for x in body.id]),
            BizNewsArticle.is_delete == 0,
        ).limit(1)
        if db.scalars(exists_stmt).first() is not None:
            return make_response(403, data={}, msg="无权限删除所选文章")
        return make_response(500, data={}, msg="文章不存在或已删除")

    db.commit()
    return make_response(200, data={}, msg="删除成功")


@router.post("/newsArticle/changeStatus", dependencies=[Depends(require_permission("newsArticle:edit"))])
def news_article_change_status(
    body: NewsArticleChangeStatusBody,
    db: Session = Depends(get_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = require_user_with_data_perm(db, x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    if body.status not in (0, 1):
        return make_response(500, data={}, msg="状态参数无效")
    aid = int(body.id) if not isinstance(body.id, int) else body.id
    stmt = select(BizNewsArticle).where(BizNewsArticle.id == aid, BizNewsArticle.is_delete == 0)
    stmt = apply_data_scope(stmt, BizNewsArticle)
    row = db.scalars(stmt).first()
    if not row:
        exists = db.scalars(
            select(BizNewsArticle.id).where(BizNewsArticle.id == aid, BizNewsArticle.is_delete == 0).limit(1)
        ).first()
        if exists is not None:
            return make_response(403, data={}, msg="无权限访问该文章")
        return make_response(500, data={}, msg="文章不存在")

    row.status = body.status
    db.commit()
    return make_response(200, data={}, msg="状态修改成功")
