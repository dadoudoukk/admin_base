from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from api.deps import get_db, make_response, require_permission, require_user
from api.helpers import compute_home_statistics, news_article_row, news_category_row
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
    ctx = require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    q = db.query(BizNewsCategory)
    if body.categoryName and body.categoryName.strip():
        q = q.filter(BizNewsCategory.category_name.like(f"%{body.categoryName.strip()}%"))

    total = q.count()
    rows = (
        q.order_by(BizNewsCategory.sort.asc(), BizNewsCategory.id.asc())
        .offset((body.pageNum - 1) * body.pageSize)
        .limit(body.pageSize)
        .all()
    )
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
    ctx = require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    if body.status not in (0, 1):
        return make_response(500, data={}, msg="状态参数无效")
    category_name = body.categoryName.strip()
    if not category_name:
        return make_response(500, data={}, msg="分类名称不能为空")
    if db.query(BizNewsCategory).filter(BizNewsCategory.category_name == category_name).first():
        return make_response(500, data={}, msg="分类名称已存在")

    db.add(
        BizNewsCategory(
            category_name=category_name,
            sort=body.sort,
            status=body.status,
            remark=body.remark,
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
    ctx = require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    if body.status not in (0, 1):
        return make_response(500, data={}, msg="状态参数无效")
    cid = int(body.id) if not isinstance(body.id, int) else body.id
    row = db.query(BizNewsCategory).filter(BizNewsCategory.id == cid).first()
    if not row:
        return make_response(500, data={}, msg="分类不存在")

    category_name = body.categoryName.strip()
    if not category_name:
        return make_response(500, data={}, msg="分类名称不能为空")
    other = (
        db.query(BizNewsCategory)
        .filter(BizNewsCategory.category_name == category_name, BizNewsCategory.id != cid)
        .first()
    )
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
    ctx = require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    deleted = 0
    for raw in body.id:
        cid = int(raw) if not isinstance(raw, int) else raw
        row = db.query(BizNewsCategory).filter(BizNewsCategory.id == cid).first()
        if row:
            db.delete(row)
            deleted += 1
    if not deleted:
        return make_response(500, data={}, msg="分类不存在或已删除")

    db.commit()
    return make_response(200, data={}, msg="删除成功")


@router.post("/newsCategory/changeStatus", dependencies=[Depends(require_permission("newsCategory:edit"))])
def news_category_change_status(
    body: NewsCategoryChangeStatusBody,
    db: Session = Depends(get_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    if body.status not in (0, 1):
        return make_response(500, data={}, msg="状态参数无效")
    cid = int(body.id) if not isinstance(body.id, int) else body.id
    row = db.query(BizNewsCategory).filter(BizNewsCategory.id == cid).first()
    if not row:
        return make_response(500, data={}, msg="分类不存在")

    row.status = body.status
    db.commit()
    return make_response(200, data={}, msg="状态修改成功")


@router.get("/newsCategory/all")
def news_category_all(
    db: Session = Depends(get_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = require_user(x_access_token)
    if not ctx:
        return make_response(401, data=[], msg="登录过期，请重新登录")

    rows = (
        db.query(BizNewsCategory)
        .filter(BizNewsCategory.status == 1)
        .order_by(BizNewsCategory.sort.asc(), BizNewsCategory.id.asc())
        .all()
    )
    data = [{"id": str(r.id), "categoryName": r.category_name} for r in rows]
    return make_response(200, data=data, msg="success")


@router.post("/newsArticle/list")
def news_article_list(
    body: NewsArticleListBody,
    db: Session = Depends(get_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    q = db.query(BizNewsArticle)
    if body.title and body.title.strip():
        q = q.filter(BizNewsArticle.title.like(f"%{body.title.strip()}%"))
    if body.categoryId is not None and str(body.categoryId).strip() != "":
        cid = int(body.categoryId) if not isinstance(body.categoryId, int) else body.categoryId
        q = q.filter(BizNewsArticle.category_id == cid)

    total = q.count()
    rows = (
        q.order_by(BizNewsArticle.is_top.desc(), BizNewsArticle.id.desc())
        .offset((body.pageNum - 1) * body.pageSize)
        .limit(body.pageSize)
        .all()
    )
    category_map = {str(c.id): c.category_name for c in db.query(BizNewsCategory).all()}
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
    ctx = require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    if body.newsType not in (0, 1) or body.isTop not in (0, 1) or body.status not in (0, 1):
        return make_response(500, data={}, msg="状态或类型参数无效")
    cid = int(body.categoryId) if not isinstance(body.categoryId, int) else body.categoryId
    if not db.query(BizNewsCategory).filter(BizNewsCategory.id == cid).first():
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
    ctx = require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    if body.newsType not in (0, 1) or body.isTop not in (0, 1) or body.status not in (0, 1):
        return make_response(500, data={}, msg="状态或类型参数无效")
    aid = int(body.id) if not isinstance(body.id, int) else body.id
    row = db.query(BizNewsArticle).filter(BizNewsArticle.id == aid).first()
    if not row:
        return make_response(500, data={}, msg="文章不存在")

    cid = int(body.categoryId) if not isinstance(body.categoryId, int) else body.categoryId
    if not db.query(BizNewsCategory).filter(BizNewsCategory.id == cid).first():
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
    ctx = require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    deleted = 0
    for raw in body.id:
        aid = int(raw) if not isinstance(raw, int) else raw
        row = db.query(BizNewsArticle).filter(BizNewsArticle.id == aid).first()
        if row:
            db.delete(row)
            deleted += 1
    if not deleted:
        return make_response(500, data={}, msg="文章不存在或已删除")

    db.commit()
    return make_response(200, data={}, msg="删除成功")


@router.post("/newsArticle/changeStatus", dependencies=[Depends(require_permission("newsArticle:edit"))])
def news_article_change_status(
    body: NewsArticleChangeStatusBody,
    db: Session = Depends(get_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    if body.status not in (0, 1):
        return make_response(500, data={}, msg="状态参数无效")
    aid = int(body.id) if not isinstance(body.id, int) else body.id
    row = db.query(BizNewsArticle).filter(BizNewsArticle.id == aid).first()
    if not row:
        return make_response(500, data={}, msg="文章不存在")

    row.status = body.status
    db.commit()
    return make_response(200, data={}, msg="状态修改成功")
