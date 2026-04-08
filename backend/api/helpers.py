from datetime import datetime
from typing import Any, Dict, List, Optional, Set

import pandas as pd
from sqlalchemy.orm import Session

from models import (
    BizFragmentCategory,
    BizFragmentContent,
    BizNewsArticle,
    BizNewsCategory,
    SysDictData,
    SysDictType,
    SysMenu,
    SysOperLog,
    SysRole,
    SysUser,
)


def menu_list_fallback() -> List[dict]:
    """数据库无可用菜单时的兜底树（至少含首页，保证能进系统）。"""
    return [
        {
            "path": "/home/index",
            "name": "home",
            "component": "/home/index",
            "meta": {
                "icon": "HomeFilled",
                "title": "首页",
                "isLink": "",
                "isHide": False,
                "isFull": False,
                "isAffix": True,
                "isKeepAlive": True,
            },
        },
        {
            "path": "/dataScreen",
            "name": "dataScreen",
            "component": "/dataScreen/index",
            "meta": {
                "icon": "Histogram",
                "title": "数据大屏",
                "isLink": "",
                "isHide": False,
                "isFull": True,
                "isAffix": False,
                "isKeepAlive": True,
            },
        },
    ]


def filter_empty_catalogs(rows: List[SysMenu]) -> List[SysMenu]:
    """去掉无 component 且无子节点的 CATALOG，避免动态路由无法挂载。"""
    if not rows:
        return rows
    parent_ids_with_child: Set[Optional[int]] = {m.parent_id for m in rows if m.parent_id is not None}
    out: List[SysMenu] = []
    for m in rows:
        if m.menu_type == "CATALOG" and not (m.component or "").strip():
            if m.id not in parent_ids_with_child:
                continue
        out.append(m)
    return out


def menu_row_to_node(m: SysMenu) -> Dict[str, Any]:
    meta = {
        "icon": m.icon or "",
        "title": m.title,
        "isLink": m.is_link or "",
        "isHide": m.is_hide,
        "isFull": m.is_full,
        "isAffix": m.is_affix,
        "isKeepAlive": m.is_keep_alive,
    }
    node: Dict[str, Any] = {
        "path": m.path or "",
        "name": m.name,
        "component": (m.component or "").strip(),
        "meta": meta,
    }
    return node


def build_menu_tree(rows: List[SysMenu]) -> List[dict]:
    """将平铺菜单行递归为父子嵌套结构（按 sort、id 排序）。"""
    if not rows:
        return []

    by_parent: Dict[Optional[int], List[SysMenu]] = {}
    for m in rows:
        by_parent.setdefault(m.parent_id, []).append(m)
    for lst in by_parent.values():
        lst.sort(key=lambda x: (x.sort, x.id))

    def walk(parent_id: Optional[int]) -> List[dict]:
        items = by_parent.get(parent_id, [])
        out: List[dict] = []
        for m in items:
            node = menu_row_to_node(m)
            children = walk(m.id)
            if children:
                node["children"] = children
            out.append(node)
        return out

    return walk(None)


def menu_node_all_tree(m: SysMenu) -> Dict[str, Any]:
    """权限树节点：带 id、label，供前端 el-tree / 菜单管理表格使用。"""
    node = menu_row_to_node(m)
    node["id"] = m.id
    node["label"] = m.title
    node["menuType"] = m.menu_type
    node["parentId"] = m.parent_id
    node["permission"] = m.permission or ""
    node["sort"] = m.sort
    node["remark"] = m.remark or ""
    return node


def build_menu_tree_all(rows: List[SysMenu]) -> List[dict]:
    """完整菜单树（含目录/菜单/按钮等），不剔除空目录。"""
    if not rows:
        return []

    by_parent: Dict[Optional[int], List[SysMenu]] = {}
    for m in rows:
        by_parent.setdefault(m.parent_id, []).append(m)
    for lst in by_parent.values():
        lst.sort(key=lambda x: (x.sort, x.id))

    def walk(parent_id: Optional[int]) -> List[dict]:
        items = by_parent.get(parent_id, [])
        out: List[dict] = []
        for m in items:
            node = menu_node_all_tree(m)
            children = walk(m.id)
            if children:
                node["children"] = children
            out.append(node)
        return out

    return walk(None)


def fetch_menu_rows_for_user(db: Session, ctx: dict) -> List[SysMenu]:
    """超级管理员 / admin 角色：查全部有效菜单；否则按角色关联菜单并补全父级链。"""
    base_q = (
        db.query(SysMenu)
        .filter(SysMenu.is_delete == 0)
        .filter(SysMenu.status == True)  # noqa: E712
        .filter(SysMenu.menu_type.in_(["CATALOG", "MENU"]))
    )

    if ctx.get("is_superuser") or "admin" in (ctx.get("roles") or []) or ctx.get("username") == "admin":
        return base_q.order_by(SysMenu.sort.asc(), SysMenu.id.asc()).all()

    uid = ctx["user_id"]
    user = db.query(SysUser).filter(SysUser.id == uid, SysUser.is_delete == 0).first()
    if not user:
        return []

    all_menus = base_q.all()
    id_to_menu = {m.id: m for m in all_menus}

    seed_ids: Set[int] = set()
    for role in user.roles:
        for m in role.menus:
            if m.status and m.menu_type in ("CATALOG", "MENU"):
                seed_ids.add(m.id)

    expanded: Set[int] = set()

    def add_with_parents(mid: int) -> None:
        if mid in expanded or mid not in id_to_menu:
            return
        obj = id_to_menu[mid]
        expanded.add(mid)
        if obj.parent_id:
            add_with_parents(obj.parent_id)

    for sid in list(seed_ids):
        add_with_parents(sid)

    rows = [id_to_menu[i] for i in expanded]
    rows.sort(key=lambda m: (m.sort, m.id))
    return rows


def auth_button_list_static() -> Dict[str, List[str]]:
    return {}


def dict_data_row(d: SysDictData) -> Dict[str, Any]:
    created = d.created_at.strftime("%Y-%m-%d %H:%M:%S") if d.created_at else ""
    updated = d.updated_at.strftime("%Y-%m-%d %H:%M:%S") if d.updated_at else ""
    return {
        "id": str(d.id),
        "dictCode": d.dict_code,
        "dictLabel": d.dict_label,
        "dictValue": d.dict_value,
        "sort": d.sort,
        "status": d.status,
        "remark": d.remark or "",
        "createdAt": created,
        "updatedAt": updated,
    }


def dict_type_row(d: SysDictType) -> Dict[str, Any]:
    created = d.created_at.strftime("%Y-%m-%d %H:%M:%S") if d.created_at else ""
    updated = d.updated_at.strftime("%Y-%m-%d %H:%M:%S") if d.updated_at else ""
    return {
        "id": str(d.id),
        "dictName": d.dict_name,
        "dictCode": d.dict_code,
        "status": 1 if d.status else 0,
        "remark": d.remark or "",
        "createTime": created,
        "updateTime": updated,
    }


def user_row(u: SysUser) -> Dict[str, Any]:
    """与 Geeker ProTable / ResUserList 对齐的字段（缺省字段补空值）。"""
    created = u.created_at.strftime("%Y-%m-%d %H:%M:%S") if u.created_at else ""
    role_ids = [r.id for r in (u.roles or [])]
    role_names = [r.name for r in (u.roles or []) if (r.name or "").strip()]
    return {
        "id": str(u.id),
        "username": u.username,
        "nickname": u.nickname or "",
        "status": 1 if u.is_active else 0,
        "createTime": created,
        "gender": str(u.gender) if u.gender else "3",
        "roleIds": role_ids,
        "roleNames": role_names,
        "idCard": "",
        "email": u.email or "",
        "phone": u.phone or "",
        "address": "",
        "avatar": u.avatar or "",
        "photo": [],
        "user": {"detail": {"age": 0}},
    }


def news_category_row(c: BizNewsCategory) -> Dict[str, Any]:
    created = c.create_time.strftime("%Y-%m-%d %H:%M:%S") if c.create_time else ""
    return {
        "id": str(c.id),
        "categoryName": c.category_name,
        "sort": c.sort,
        "status": 1 if int(c.status) == 1 else 0,
        "remark": c.remark or "",
        "createTime": created,
    }


def news_article_row(a: BizNewsArticle, category_name: str = "") -> Dict[str, Any]:
    created = a.create_time.strftime("%Y-%m-%d %H:%M:%S") if a.create_time else ""
    return {
        "id": str(a.id),
        "categoryId": str(a.category_id),
        "categoryName": category_name,
        "title": a.title,
        "author": a.author or "",
        "newsType": a.news_type,
        "content": a.content or "",
        "redirectUrl": a.redirect_url or "",
        "imageUrl": a.cover_image_url or "",
        "isTop": a.is_top,
        "status": a.status,
        "createTime": created,
    }


def fragment_category_row(c: BizFragmentCategory) -> Dict[str, Any]:
    created = c.create_time.strftime("%Y-%m-%d %H:%M:%S") if c.create_time else ""
    return {
        "id": str(c.id),
        "code": c.code,
        "name": c.name,
        "remark": c.remark or "",
        "createTime": created,
    }


def fragment_content_row(r: BizFragmentContent) -> Dict[str, Any]:
    created = r.create_time.strftime("%Y-%m-%d %H:%M:%S") if r.create_time else ""
    return {
        "id": str(r.id),
        "categoryId": str(r.category_id),
        "title": r.title,
        "imageUrl": r.image_url or "",
        "linkUrl": r.link_url or "",
        "content": r.content or "",
        "sort": r.sort,
        "status": 1 if int(r.status) == 1 else 0,
        "createTime": created,
    }


def oper_log_row(r: SysOperLog) -> Dict[str, Any]:
    created = r.create_time.strftime("%Y-%m-%d %H:%M:%S") if r.create_time else ""
    return {
        "id": str(r.id),
        "userName": r.user_name or "",
        "requestMethod": r.request_method,
        "requestUrl": r.request_url,
        "requestIp": r.request_ip,
        "executeTime": r.execute_time,
        "status": 1 if int(r.status) == 1 else 0,
        "errorMsg": r.error_msg or "",
        "requestParam": r.request_param or "",
        "createTime": created,
    }


def parse_datetime_text(raw: Optional[str]) -> Optional[datetime]:
    text = (raw or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def build_sys_log_export_query(
    db: Session,
    user_name: Optional[str],
    request_method: Optional[str],
    start_time: Optional[str],
    end_time: Optional[str],
):
    q = db.query(SysOperLog).filter(SysOperLog.is_delete == 0)
    if user_name and user_name.strip():
        q = q.filter(SysOperLog.user_name.like(f"%{user_name.strip()}%"))
    if request_method and request_method.strip():
        q = q.filter(SysOperLog.request_method == request_method.strip().upper())

    start_dt = parse_datetime_text(start_time)
    end_dt = parse_datetime_text(end_time)
    if start_dt is not None:
        q = q.filter(SysOperLog.create_time >= start_dt)
    if end_dt is not None:
        q = q.filter(SysOperLog.create_time <= end_dt)
    return q.order_by(SysOperLog.create_time.desc())


def role_row(r: SysRole) -> Dict[str, Any]:
    created = r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else ""
    return {
        "id": str(r.id),
        "roleName": r.name,
        "roleCode": r.code,
        "remark": r.description or "",
        "status": 1 if r.is_active else 0,
        "createTime": created,
    }


def safe_cell_to_str(val: Any) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    return str(val).strip()


def gender_to_label(gender: Optional[str]) -> str:
    gv = str(gender or "3").strip()
    return {"1": "男", "2": "女", "3": "未知"}.get(gv, "未知")


def gender_to_value(gender_label: str) -> str:
    label = (gender_label or "").strip()
    mapping = {
        "男": "1",
        "1": "1",
        "女": "2",
        "2": "2",
        "未知": "3",
        "3": "3",
    }
    return mapping.get(label, "3")


def prepare_user_export_query(db: Session, username: Optional[str], gender: Optional[str]):
    q = db.query(SysUser).filter(SysUser.is_delete == 0)
    if username and username.strip():
        q = q.filter(SysUser.username.like(f"%{username.strip()}%"))
    if gender is not None and str(gender).strip() != "":
        q = q.filter(SysUser.gender == str(gender).strip())
    return q.order_by(SysUser.id.desc())


def query_menu_tree_for_manage(db: Session) -> List[dict]:
    """菜单管理：返回全部菜单（含停用）树。"""
    rows = (
        db.query(SysMenu)
        .filter(SysMenu.is_delete == 0)
        .order_by(SysMenu.sort.asc(), SysMenu.id.asc())
        .all()
    )
    return build_menu_tree_all(rows)


def compute_home_statistics(db: Session) -> Dict[str, Any]:
    return {
        "userCount": db.query(SysUser).filter(SysUser.is_delete == 0).count(),
        "roleCount": db.query(SysRole).filter(SysRole.is_delete == 0).count(),
        "menuCount": db.query(SysMenu).filter(SysMenu.is_delete == 0).count(),
        "newsArticleCount": db.query(BizNewsArticle).filter(BizNewsArticle.is_delete == 0).count(),
        "newsCategoryCount": db.query(BizNewsCategory).filter(BizNewsCategory.is_delete == 0).count(),
        "fragmentContentCount": db.query(BizFragmentContent).filter(BizFragmentContent.is_delete == 0).count(),
        "operLogCount": db.query(SysOperLog).filter(SysOperLog.is_delete == 0).count(),
    }
