import asyncio
import logging
import os
import shutil
import time
import traceback
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

import jwt
from fastapi import APIRouter, Depends, FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from passlib.context import CryptContext
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.config import get_settings
from core.database import SessionLocal
from core.redis_client import cache_delete, cache_get_or_set_json, cache_set_json
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
    SysRoleMenu,
    SysUser,
)

logger = logging.getLogger(__name__)
_settings = get_settings()

# ========== 本地上传目录（backend/uploads）==========
_BACKEND_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = _BACKEND_DIR / "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ========== JWT / 默认头像（见 core.config.Settings）==========

# ========== 密码（与 init_db 一致：bcrypt）==========
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def make_response(code: int, data: Any = None, msg: str = "success") -> Dict[str, Any]:
    return {"code": code, "data": data, "msg": msg}


def create_access_token(user_id: int) -> str:
    """生成 JWT：payload 包含 user_id、iat、exp（过期时间）。"""
    now = int(time.time())
    payload = {
        "user_id": user_id,
        "iat": now,
        "exp": now + _settings.access_token_expire_seconds,
    }
    return jwt.encode(payload, _settings.secret_key, algorithm=_settings.jwt_algorithm)


def decode_access_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, _settings.secret_key, algorithms=[_settings.jwt_algorithm])
    except jwt.PyJWTError:
        return None


def require_user(x_access_token: Optional[str]) -> Optional[dict]:
    if not x_access_token:
        return None
    claims = decode_access_token(x_access_token)
    if not claims:
        return None
    user_id = claims.get("user_id")
    if user_id is None:
        return None

    db = SessionLocal()
    try:
        user = db.query(SysUser).filter(SysUser.id == user_id).first()
        if not user or not user.is_active:
            return None
        role_name = ""
        role_codes: List[str] = []
        if user.roles:
            role_name = user.roles[0].name
            role_codes = [r.code for r in user.roles]
        return {
            "user_id": user.id,
            "username": user.username,
            "avatar": user.avatar,
            "roleName": role_name,
            "roles": role_codes,
            "is_superuser": user.is_superuser,
        }
    finally:
        db.close()


def fetch_button_menus_for_user(db: Session, ctx: dict) -> List[SysMenu]:
    q = db.query(SysMenu).filter(SysMenu.status == True).filter(SysMenu.menu_type == "BUTTON")  # noqa: E712
    if ctx.get("is_superuser") or "admin" in (ctx.get("roles") or []) or ctx.get("username") == "admin":
        return q.order_by(SysMenu.sort.asc(), SysMenu.id.asc()).all()

    uid = ctx["user_id"]
    user = db.query(SysUser).filter(SysUser.id == uid).first()
    if not user:
        return []

    merged: Dict[int, SysMenu] = {}
    for role in user.roles:
        for m in role.menus:
            if m.status and m.menu_type == "BUTTON":
                merged[m.id] = m
    out = list(merged.values())
    out.sort(key=lambda m: (m.sort, m.id))
    return out


def _button_code(m: SysMenu) -> str:
    return ((m.name or "").strip() or (m.permission or "").strip() or (m.path or "").strip())


def _button_owner_page_name(m: SysMenu) -> str:
    cur: Optional[SysMenu] = m.parent
    while cur:
        if cur.menu_type in ("MENU", "CATALOG") and (cur.name or "").strip():
            return cur.name.strip()
        cur = cur.parent
    return "global"


def build_auth_button_map(rows: List[SysMenu]) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    for m in rows:
        code = _button_code(m)
        if not code:
            continue
        page_name = _button_owner_page_name(m)
        out.setdefault(page_name, [])
        if code not in out[page_name]:
            out[page_name].append(code)
    return out


def build_auth_button_codes(rows: List[SysMenu]) -> List[str]:
    out: List[str] = []
    for m in rows:
        code = _button_code(m)
        if code and code not in out:
            out.append(code)
    return out


def _load_user_perms_bundle(db: Session, ctx: dict) -> Dict[str, Any]:
    rows = fetch_button_menus_for_user(db, ctx)
    return {
        "codes": build_auth_button_codes(rows),
        "buttonMap": build_auth_button_map(rows),
    }


def get_user_perms_bundle(db: Session, ctx: dict) -> Dict[str, Any]:
    key = f"user:perms:{ctx['user_id']}"

    def load() -> Dict[str, Any]:
        return _load_user_perms_bundle(db, ctx)

    return cache_get_or_set_json(key, 3600, load)


def _invalidate_dict_cache(dict_code: Optional[str]) -> None:
    c = (dict_code or "").strip()
    if c:
        cache_delete(f"dict:data:{c}")


def _compute_home_statistics(db: Session) -> Dict[str, Any]:
    return {
        "userCount": db.query(SysUser).count(),
        "roleCount": db.query(SysRole).count(),
        "menuCount": db.query(SysMenu).count(),
        "newsArticleCount": db.query(BizNewsArticle).count(),
        "newsCategoryCount": db.query(BizNewsCategory).count(),
        "fragmentContentCount": db.query(BizFragmentContent).count(),
        "operLogCount": db.query(SysOperLog).count(),
    }


def require_permission(permission_code: str):
    def _checker(
        x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
        db: Session = Depends(get_db),
    ) -> bool:
        ctx = require_user(x_access_token)
        if not ctx:
            raise HTTPException(status_code=401, detail="登录过期，请重新登录")
        bundle = get_user_perms_bundle(db, ctx)
        codes = set(bundle.get("codes") or [])
        if permission_code not in codes:
            raise HTTPException(status_code=403, detail="无权限访问")
        return True

    return _checker


class LoginBody(BaseModel):
    username: str = Field(..., min_length=1, description="登录账号")
    password: str = Field(..., min_length=1, description="明文密码")


class UserListBody(BaseModel):
    pageNum: int = Field(1, ge=1, description="当前页码")
    pageSize: int = Field(10, ge=1, le=200, description="每页条数")
    username: Optional[str] = Field(None, description="账号模糊搜索")
    gender: Optional[str] = Field(None, description="性别字典值，如 1/2/3")


class UserAddBody(BaseModel):
    username: str = Field(..., min_length=1, description="登录账号")
    password: str = Field(..., min_length=1, description="明文密码")
    nickname: Optional[str] = Field(None, description="昵称")
    email: Optional[str] = Field(None, description="邮箱")
    phone: Optional[str] = Field(None, description="手机")
    gender: Optional[str] = Field("3", description="性别字典值，默认 3 未知")
    roleIds: List[int] = Field(default_factory=list, description="角色 ID 列表")


class UserDeleteBody(BaseModel):
    id: List[Union[str, int]] = Field(..., min_length=1, description="待删除用户 ID 列表")


class UserEditBody(BaseModel):
    id: Union[str, int] = Field(..., description="用户 ID")
    username: Optional[str] = Field(None, description="登录账号")
    nickname: Optional[str] = Field(None, description="昵称")
    email: Optional[str] = Field(None, description="邮箱")
    phone: Optional[str] = Field(None, description="手机")
    gender: Optional[str] = Field(None, description="性别字典值")
    roleIds: List[int] = Field(default_factory=list, description="角色 ID 列表")


class UserChangeStatusBody(BaseModel):
    id: Union[str, int] = Field(..., description="用户 ID")
    status: int = Field(..., description="1 启用 0 禁用")


class UserChangePasswordBody(BaseModel):
    oldPassword: str = Field(..., min_length=1, description="旧密码")
    newPassword: str = Field(..., min_length=1, description="新密码")


class RoleListBody(BaseModel):
    pageNum: int = Field(1, ge=1)
    pageSize: int = Field(10, ge=1, le=200)
    roleName: Optional[str] = Field(None, description="角色名称模糊")
    roleCode: Optional[str] = Field(None, description="角色标识模糊")


class RoleAddBody(BaseModel):
    roleName: str = Field(..., min_length=1, description="角色名称")
    roleCode: str = Field(..., min_length=1, description="角色标识")
    remark: Optional[str] = Field(None, description="备注")


class RoleEditBody(BaseModel):
    id: Union[str, int] = Field(..., description="角色 ID")
    roleName: str = Field(..., min_length=1)
    roleCode: str = Field(..., min_length=1)
    remark: Optional[str] = Field(None, description="备注")


class RoleDeleteBody(BaseModel):
    id: List[Union[str, int]] = Field(..., min_length=1, description="角色 ID 列表")


class RoleMenuIdsBody(BaseModel):
    roleId: Union[str, int] = Field(..., description="角色 ID")


class RoleAssignMenuBody(BaseModel):
    roleId: Union[str, int] = Field(..., description="角色 ID")
    menuIds: List[int] = Field(default_factory=list, description="菜单 ID 列表")


_MENU_TYPES = frozenset({"CATALOG", "MENU", "BUTTON"})


class MenuAddBody(BaseModel):
    parentId: Optional[int] = Field(None, description="父级菜单 ID，根节点不传")
    menuType: str = Field("MENU", description="CATALOG / MENU / BUTTON")
    name: str = Field(..., min_length=1, description="路由 name")
    title: str = Field(..., min_length=1, description="显示标题")
    path: Optional[str] = None
    component: Optional[str] = None
    icon: Optional[str] = None
    sort: int = 0
    remark: Optional[str] = None


class MenuEditBody(BaseModel):
    id: Union[str, int]
    parentId: Optional[int] = None
    menuType: Optional[str] = None
    name: Optional[str] = None
    title: Optional[str] = None
    path: Optional[str] = None
    component: Optional[str] = None
    icon: Optional[str] = None
    sort: Optional[int] = None
    remark: Optional[str] = None
    status: Optional[bool] = None


class MenuDeleteBody(BaseModel):
    id: Union[str, int] = Field(..., description="菜单 ID")


class DictTypeListBody(BaseModel):
    pageNum: int = Field(1, ge=1, description="当前页码")
    pageSize: int = Field(10, ge=1, le=200, description="每页条数")
    dictName: Optional[str] = Field(None, description="字典名称模糊搜索")
    dictCode: Optional[str] = Field(None, description="字典编码模糊搜索")


class DictTypeAddBody(BaseModel):
    dictName: str = Field(..., min_length=1, description="字典名称")
    dictCode: str = Field(..., min_length=1, description="字典编码")
    status: Optional[bool] = Field(True, description="状态")
    remark: Optional[str] = Field(None, description="备注")


class DictTypeEditBody(BaseModel):
    id: Union[str, int] = Field(..., description="字典类型 ID")
    dictName: str = Field(..., min_length=1, description="字典名称")
    dictCode: str = Field(..., min_length=1, description="字典编码")
    status: Optional[bool] = Field(True, description="状态")
    remark: Optional[str] = Field(None, description="备注")


class DictTypeDeleteBody(BaseModel):
    id: List[Union[str, int]] = Field(..., min_length=1, description="待删除字典类型 ID 列表")


class DictTypeChangeStatusBody(BaseModel):
    id: Union[str, int] = Field(..., description="字典类型 ID")
    status: Union[bool, int] = Field(..., description="状态（true/false 或 1/0）")


class DictDataListBody(BaseModel):
    pageNum: int = Field(1, ge=1, description="当前页码")
    pageSize: int = Field(10, ge=1, le=200, description="每页条数")
    dictCode: str = Field(..., min_length=1, description="字典编码（必填）")
    dictLabel: Optional[str] = Field(None, description="字典标签模糊搜索")
    dictValue: Optional[str] = Field(None, description="字典值模糊搜索")


class DictDataAddBody(BaseModel):
    dictCode: str = Field(..., min_length=1, description="字典编码")
    dictLabel: str = Field(..., min_length=1, description="字典标签")
    dictValue: str = Field(..., min_length=1, description="字典值")
    sort: int = Field(0, description="排序")
    status: Optional[bool] = Field(True, description="状态")
    remark: Optional[str] = Field(None, description="备注")


class DictDataEditBody(BaseModel):
    id: Union[str, int] = Field(..., description="字典数据 ID")
    dictCode: str = Field(..., min_length=1, description="字典编码")
    dictLabel: str = Field(..., min_length=1, description="字典标签")
    dictValue: str = Field(..., min_length=1, description="字典值")
    sort: int = Field(0, description="排序")
    status: Optional[bool] = Field(True, description="状态")
    remark: Optional[str] = Field(None, description="备注")


class DictDataDeleteBody(BaseModel):
    id: List[Union[str, int]] = Field(..., min_length=1, description="待删除字典数据 ID 列表")


class DictDataChangeStatusBody(BaseModel):
    id: Union[str, int] = Field(..., description="字典数据 ID")
    status: Union[bool, int] = Field(..., description="状态（true/false 或 1/0）")


class NewsCategoryListBody(BaseModel):
    pageNum: int = Field(1, ge=1, description="当前页码")
    pageSize: int = Field(10, ge=1, le=200, description="每页条数")
    categoryName: Optional[str] = Field(None, description="分类名称模糊搜索")


class NewsCategoryAddBody(BaseModel):
    categoryName: str = Field(..., min_length=1, description="分类名称")
    sort: int = Field(0, description="排序")
    status: int = Field(1, description="状态：0停用 1启用")
    remark: Optional[str] = Field(None, description="备注")


class NewsCategoryEditBody(BaseModel):
    id: Union[str, int] = Field(..., description="分类 ID")
    categoryName: str = Field(..., min_length=1, description="分类名称")
    sort: int = Field(0, description="排序")
    status: int = Field(1, description="状态：0停用 1启用")
    remark: Optional[str] = Field(None, description="备注")


class NewsCategoryDeleteBody(BaseModel):
    id: List[Union[str, int]] = Field(..., min_length=1, description="待删除分类 ID 列表")


class NewsCategoryChangeStatusBody(BaseModel):
    id: Union[str, int] = Field(..., description="分类 ID")
    status: int = Field(..., description="状态：0停用 1启用")


class NewsArticleListBody(BaseModel):
    pageNum: int = Field(1, ge=1, description="当前页码")
    pageSize: int = Field(10, ge=1, le=200, description="每页条数")
    title: Optional[str] = Field(None, description="标题模糊搜索")
    categoryId: Optional[Union[str, int]] = Field(None, description="分类 ID")


class NewsArticleAddBody(BaseModel):
    categoryId: Union[str, int] = Field(..., description="分类 ID")
    title: str = Field(..., min_length=1, description="新闻标题")
    author: Optional[str] = Field(None, description="作者")
    newsType: int = Field(0, description="类型：0图文内容 1外部跳转")
    content: Optional[str] = Field(None, description="正文内容")
    redirectUrl: Optional[str] = Field(None, description="跳转链接")
    imageUrl: Optional[str] = Field(None, description="封面图 URL")
    isTop: int = Field(0, description="是否置顶：0否 1是")
    status: int = Field(1, description="状态：0下架 1发布")


class NewsArticleEditBody(BaseModel):
    id: Union[str, int] = Field(..., description="文章 ID")
    categoryId: Union[str, int] = Field(..., description="分类 ID")
    title: str = Field(..., min_length=1, description="新闻标题")
    author: Optional[str] = Field(None, description="作者")
    newsType: int = Field(0, description="类型：0图文内容 1外部跳转")
    content: Optional[str] = Field(None, description="正文内容")
    redirectUrl: Optional[str] = Field(None, description="跳转链接")
    imageUrl: Optional[str] = Field(None, description="封面图 URL")
    isTop: int = Field(0, description="是否置顶：0否 1是")
    status: int = Field(1, description="状态：0下架 1发布")


class NewsArticleDeleteBody(BaseModel):
    id: List[Union[str, int]] = Field(..., min_length=1, description="待删除文章 ID 列表")


class NewsArticleChangeStatusBody(BaseModel):
    id: Union[str, int] = Field(..., description="文章 ID")
    status: int = Field(..., description="状态：0下架 1发布")


class FragmentCategoryListBody(BaseModel):
    pageNum: int = Field(1, ge=1, description="当前页码")
    pageSize: int = Field(10, ge=1, le=200, description="每页条数")
    code: Optional[str] = Field(None, description="标识码模糊搜索")
    name: Optional[str] = Field(None, description="位置名称模糊搜索")


class FragmentCategoryAddBody(BaseModel):
    code: str = Field(..., min_length=1, description="标识码")
    name: str = Field(..., min_length=1, description="位置名称")
    remark: Optional[str] = Field(None, description="备注")


class FragmentCategoryEditBody(BaseModel):
    id: Union[str, int] = Field(..., description="位置 ID")
    code: str = Field(..., min_length=1, description="标识码")
    name: str = Field(..., min_length=1, description="位置名称")
    remark: Optional[str] = Field(None, description="备注")


class FragmentCategoryDeleteBody(BaseModel):
    id: List[Union[str, int]] = Field(..., min_length=1, description="待删除位置 ID 列表")


class FragmentContentListBody(BaseModel):
    pageNum: int = Field(1, ge=1, description="当前页码")
    pageSize: int = Field(10, ge=1, le=200, description="每页条数")
    categoryId: Optional[Union[str, int]] = Field(None, description="碎片位置 ID，筛选")
    title: Optional[str] = Field(None, description="标题模糊搜索")


class FragmentContentAddBody(BaseModel):
    categoryId: Union[str, int] = Field(..., description="碎片位置 ID")
    title: str = Field(..., min_length=1, description="标题")
    imageUrl: Optional[str] = Field(None, description="图片链接")
    linkUrl: Optional[str] = Field(None, description="跳转链接")
    content: Optional[str] = Field(None, description="文本内容")
    sort: int = Field(0, description="排序")
    status: int = Field(1, description="状态：0下线 1上线")


class FragmentContentEditBody(BaseModel):
    id: Union[str, int] = Field(..., description="内容 ID")
    title: str = Field(..., min_length=1, description="标题")
    imageUrl: Optional[str] = Field(None, description="图片链接")
    linkUrl: Optional[str] = Field(None, description="跳转链接")
    content: Optional[str] = Field(None, description="文本内容")
    sort: int = Field(0, description="排序")
    status: int = Field(1, description="状态：0下线 1上线")


class FragmentContentDeleteBody(BaseModel):
    id: List[Union[str, int]] = Field(..., min_length=1, description="待删除内容 ID 列表")


class FragmentContentChangeStatusBody(BaseModel):
    id: Union[str, int] = Field(..., description="内容 ID")
    status: int = Field(..., description="状态：0下线 1上线")


class SysOperLogListBody(BaseModel):
    pageNum: int = Field(1, ge=1, description="当前页码")
    pageSize: int = Field(10, ge=1, le=200, description="每页条数")
    userName: Optional[str] = Field(None, description="操作人模糊搜索")
    requestMethod: Optional[str] = Field(None, description="请求方式，如 POST")


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


def _filter_empty_catalogs(rows: List[SysMenu]) -> List[SysMenu]:
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


def _menu_row_to_node(m: SysMenu) -> Dict[str, Any]:
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
            node = _menu_row_to_node(m)
            children = walk(m.id)
            if children:
                node["children"] = children
            out.append(node)
        return out

    return walk(None)


def _menu_node_all_tree(m: SysMenu) -> Dict[str, Any]:
    """权限树节点：带 id、label，供前端 el-tree / 菜单管理表格使用。"""
    node = _menu_row_to_node(m)
    node["id"] = m.id
    node["label"] = m.title
    node["menuType"] = m.menu_type
    node["parentId"] = m.parent_id
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
            node = _menu_node_all_tree(m)
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
        .filter(SysMenu.status == True)  # noqa: E712
        .filter(SysMenu.menu_type.in_(["CATALOG", "MENU"]))
    )

    if ctx.get("is_superuser") or "admin" in (ctx.get("roles") or []) or ctx.get("username") == "admin":
        return base_q.order_by(SysMenu.sort.asc(), SysMenu.id.asc()).all()

    uid = ctx["user_id"]
    user = db.query(SysUser).filter(SysUser.id == uid).first()
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


def _dict_data_row(d: SysDictData) -> Dict[str, Any]:
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


def _dict_type_row(d: SysDictType) -> Dict[str, Any]:
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


def _user_row(u: SysUser) -> Dict[str, Any]:
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


def _news_category_row(c: BizNewsCategory) -> Dict[str, Any]:
    created = c.create_time.strftime("%Y-%m-%d %H:%M:%S") if c.create_time else ""
    return {
        "id": str(c.id),
        "categoryName": c.category_name,
        "sort": c.sort,
        "status": 1 if int(c.status) == 1 else 0,
        "remark": c.remark or "",
        "createTime": created,
    }


def _news_article_row(a: BizNewsArticle, category_name: str = "") -> Dict[str, Any]:
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


def _fragment_category_row(c: BizFragmentCategory) -> Dict[str, Any]:
    created = c.create_time.strftime("%Y-%m-%d %H:%M:%S") if c.create_time else ""
    return {
        "id": str(c.id),
        "code": c.code,
        "name": c.name,
        "remark": c.remark or "",
        "createTime": created,
    }


def _fragment_content_row(r: BizFragmentContent) -> Dict[str, Any]:
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


def _oper_log_row(r: SysOperLog) -> Dict[str, Any]:
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


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64]
    if request.client:
        return (request.client.host or "")[:64]
    return ""


def _save_oper_log_sync(
    access_token: Optional[str],
    request_method: str,
    request_url: str,
    request_ip: str,
    execute_time: int,
    status: int,
    error_msg: Optional[str],
    request_param: Optional[str],
) -> None:
    """仅在函数内创建 Session，禁止复用外部传入的 Session（线程安全）。"""
    db = SessionLocal()
    try:
        user_name: Optional[str] = None
        if access_token:
            claims = decode_access_token(access_token)
            if claims and claims.get("user_id") is not None:
                u = db.query(SysUser).filter(SysUser.id == int(claims["user_id"])).first()
                if u:
                    user_name = u.username
        db.add(
            SysOperLog(
                user_name=user_name,
                request_method=request_method,
                request_url=request_url,
                request_ip=request_ip,
                execute_time=execute_time,
                status=status,
                error_msg=error_msg,
                request_param=request_param,
            )
        )
        db.commit()
    except Exception:
        logger.exception("写入操作日志失败")
        db.rollback()
    finally:
        db.close()


def _resolve_oper_log_status(response: Optional[Response], err: Optional[Exception]) -> tuple[int, Optional[str]]:
    if err is not None:
        return 0, (str(err) or "error")[:2000]
    if response is None:
        return 0, None
    raw = response.headers.get("x-geeker-code")
    if raw is not None:
        try:
            code = int(raw)
            return (1 if code == 200 else 0, None)
        except ValueError:
            return 1, None
    if response.status_code >= 400:
        return 0, f"HTTP {response.status_code}"
    return 1, None


async def _flush_oper_log_background(
    access_token: Optional[str],
    request_method: str,
    request_url: str,
    request_ip: str,
    execute_time_ms: int,
    status: int,
    error_msg: Optional[str],
    request_param: Optional[str],
) -> None:
    def _run() -> None:
        _save_oper_log_sync(
            access_token,
            request_method,
            request_url,
            request_ip,
            execute_time_ms,
            status,
            error_msg,
            request_param,
        )

    try:
        await asyncio.to_thread(_run)
    except Exception:
        logger.exception("异步写入操作日志失败")


geeker_router = APIRouter(prefix="/geeker")
api_router = APIRouter(prefix="/api")


@geeker_router.post("/login")
@api_router.post("/login")
def login(body: LoginBody, db: Session = Depends(get_db)) -> Dict[str, Any]:
    username = body.username.strip()
    user = db.query(SysUser).filter(SysUser.username == username).first()
    if not user:
        return make_response(500, data={}, msg="用户名或密码错误")
    if not pwd_context.verify(body.password, user.password):
        return make_response(500, data={}, msg="用户名或密码错误")

    token = create_access_token(user.id)
    return make_response(200, data={"access_token": token}, msg="登录成功")


@geeker_router.get("/menu/list")
@api_router.get("/menu/list")
def menu_list(
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    ctx = require_user(x_access_token)
    if not ctx:
        return make_response(401, data=[], msg="登录过期，请重新登录")

    rows = fetch_menu_rows_for_user(db, ctx)
    rows = _filter_empty_catalogs(rows)
    tree = build_menu_tree(rows)
    if not tree:
        tree = menu_list_fallback()
    return make_response(200, data=tree, msg="success")


@geeker_router.get("/auth/buttons")
@api_router.get("/auth/buttons")
def auth_buttons(
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    ctx = require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")
    bundle = get_user_perms_bundle(db, ctx)
    return make_response(200, data=bundle.get("buttonMap") or {}, msg="success")


@geeker_router.get("/dict/data/{dict_code}")
@api_router.get("/dict/data/{dict_code}")
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
        return [_dict_data_row(r) for r in rows]

    key = f"dict:data:{code}"
    data = cache_get_or_set_json(key, None, load)
    return make_response(200, data=data, msg="success")


@geeker_router.post("/dict/type/list")
@api_router.post("/dict/type/list")
def dict_type_list(
    body: DictTypeListBody,
    db: Session = Depends(get_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    q = db.query(SysDictType)
    if body.dictName and body.dictName.strip():
        kw = f"%{body.dictName.strip()}%"
        q = q.filter(SysDictType.dict_name.like(kw))
    if body.dictCode and body.dictCode.strip():
        kw = f"%{body.dictCode.strip()}%"
        q = q.filter(SysDictType.dict_code.like(kw))

    total = q.count()
    rows = (
        q.order_by(SysDictType.id.desc())
        .offset((body.pageNum - 1) * body.pageSize)
        .limit(body.pageSize)
        .all()
    )
    return make_response(
        200,
        data={
            "list": [_dict_type_row(r) for r in rows],
            "pageNum": body.pageNum,
            "pageSize": body.pageSize,
            "total": total,
        },
        msg="success",
    )


@geeker_router.post("/dict/type/add", dependencies=[Depends(require_permission("dictType:add"))])
@api_router.post("/dict/type/add", dependencies=[Depends(require_permission("dictType:add"))])
def dict_type_add(
    body: DictTypeAddBody,
    db: Session = Depends(get_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    dict_name = body.dictName.strip()
    dict_code = body.dictCode.strip()
    if db.query(SysDictType).filter(SysDictType.dict_code == dict_code).first():
        return make_response(500, data={}, msg="字典编码已存在")

    db.add(
        SysDictType(
            dict_name=dict_name,
            dict_code=dict_code,
            status=bool(body.status),
            remark=body.remark,
        )
    )
    db.commit()
    return make_response(200, data={}, msg="新增成功")


@geeker_router.post("/dict/type/edit", dependencies=[Depends(require_permission("dictType:edit"))])
@api_router.post("/dict/type/edit", dependencies=[Depends(require_permission("dictType:edit"))])
def dict_type_edit(
    body: DictTypeEditBody,
    db: Session = Depends(get_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    did = int(body.id) if not isinstance(body.id, int) else body.id
    row = db.query(SysDictType).filter(SysDictType.id == did).first()
    if not row:
        return make_response(500, data={}, msg="字典类型不存在")

    old_code = row.dict_code
    dict_name = body.dictName.strip()
    dict_code = body.dictCode.strip()
    other = db.query(SysDictType).filter(SysDictType.dict_code == dict_code, SysDictType.id != did).first()
    if other:
        return make_response(500, data={}, msg="字典编码已存在")

    row.dict_name = dict_name
    row.dict_code = dict_code
    row.status = bool(body.status)
    row.remark = body.remark
    db.commit()
    _invalidate_dict_cache(old_code)
    if dict_code != old_code:
        _invalidate_dict_cache(dict_code)
    return make_response(200, data={}, msg="编辑成功")


@geeker_router.post("/dict/type/delete", dependencies=[Depends(require_permission("dictType:delete"))])
@api_router.post("/dict/type/delete", dependencies=[Depends(require_permission("dictType:delete"))])
def dict_type_delete(
    body: DictTypeDeleteBody,
    db: Session = Depends(get_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    deleted = 0
    for raw in body.id:
        did = int(raw) if not isinstance(raw, int) else raw
        row = db.query(SysDictType).filter(SysDictType.id == did).first()
        if not row:
            continue
        _invalidate_dict_cache(row.dict_code)
        db.query(SysDictData).filter(SysDictData.dict_code == row.dict_code).delete()
        db.delete(row)
        deleted += 1
    if not deleted:
        return make_response(500, data={}, msg="字典类型不存在或已删除")

    db.commit()
    return make_response(200, data={}, msg="删除成功")


@geeker_router.post("/dict/type/changeStatus", dependencies=[Depends(require_permission("dictType:edit"))])
@api_router.post("/dict/type/changeStatus", dependencies=[Depends(require_permission("dictType:edit"))])
def dict_type_change_status(
    body: DictTypeChangeStatusBody,
    db: Session = Depends(get_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    did = int(body.id) if not isinstance(body.id, int) else body.id
    row = db.query(SysDictType).filter(SysDictType.id == did).first()
    if not row:
        return make_response(500, data={}, msg="字典类型不存在")

    row.status = bool(body.status)
    db.commit()
    _invalidate_dict_cache(row.dict_code)
    return make_response(200, data={}, msg="状态修改成功")


@geeker_router.post("/dict/data/list")
@api_router.post("/dict/data/list")
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
            "list": [_dict_data_row(r) for r in rows],
            "pageNum": body.pageNum,
            "pageSize": body.pageSize,
            "total": total,
        },
        msg="success",
    )


@geeker_router.post("/dict/data/add", dependencies=[Depends(require_permission("dictData:add"))])
@api_router.post("/dict/data/add", dependencies=[Depends(require_permission("dictData:add"))])
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
    _invalidate_dict_cache(code)
    return make_response(200, data={}, msg="新增成功")


@geeker_router.post("/dict/data/edit", dependencies=[Depends(require_permission("dictData:edit"))])
@api_router.post("/dict/data/edit", dependencies=[Depends(require_permission("dictData:edit"))])
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
    _invalidate_dict_cache(prev_code)
    if code != prev_code:
        _invalidate_dict_cache(code)
    return make_response(200, data={}, msg="编辑成功")


@geeker_router.post("/dict/data/delete", dependencies=[Depends(require_permission("dictData:delete"))])
@api_router.post("/dict/data/delete", dependencies=[Depends(require_permission("dictData:delete"))])
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
        _invalidate_dict_cache(c)
    return make_response(200, data={}, msg="删除成功")


@geeker_router.post("/dict/data/changeStatus", dependencies=[Depends(require_permission("dictData:edit"))])
@api_router.post("/dict/data/changeStatus", dependencies=[Depends(require_permission("dictData:edit"))])
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
    _invalidate_dict_cache(row.dict_code)
    return make_response(200, data={}, msg="状态修改成功")


@geeker_router.get("/user/info")
@api_router.get("/user/info")
def user_info(x_access_token: Optional[str] = Header(default=None, alias="x-access-token")) -> Dict[str, Any]:
    ctx = require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    db = SessionLocal()
    try:
        bundle = get_user_perms_bundle(db, ctx)
        buttons = bundle.get("codes") or []
    finally:
        db.close()

    data = {
        "id": str(ctx["user_id"]),
        "name": ctx["username"],
        "avatar": ctx.get("avatar") or _settings.default_avatar_url,
        "roles": ctx.get("roles") or [],
        "roleName": ctx.get("roleName") or "管理员",
        "buttons": buttons,
    }
    return make_response(200, data=data, msg="success")


@geeker_router.post("/user/changePassword")
@api_router.post("/user/changePassword")
def user_change_password(
    body: UserChangePasswordBody,
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    ctx = require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    user = db.query(SysUser).filter(SysUser.id == ctx["user_id"]).first()
    if not user:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    if not pwd_context.verify(body.oldPassword, user.password):
        return make_response(500, data={}, msg="原密码不正确")

    user.password = pwd_context.hash(body.newPassword)
    db.commit()
    return make_response(200, data={}, msg="密码修改成功，请重新登录")


@geeker_router.post("/logout")
@api_router.post("/logout")
def logout() -> Dict[str, Any]:
    return make_response(200, data={}, msg="退出成功")


@geeker_router.post("/user/list")
@api_router.post("/user/list")
def user_list_page(
    body: UserListBody,
    db: Session = Depends(get_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    q = db.query(SysUser)
    if body.username and body.username.strip():
        kw = f"%{body.username.strip()}%"
        q = q.filter(SysUser.username.like(kw))
    if body.gender is not None and str(body.gender).strip() != "":
        q = q.filter(SysUser.gender == str(body.gender).strip())

    total = q.count()
    page_num = body.pageNum
    page_size = body.pageSize
    rows = (
        q.order_by(SysUser.id.desc())
        .offset((page_num - 1) * page_size)
        .limit(page_size)
        .all()
    )

    data = {
        "list": [_user_row(u) for u in rows],
        "pageNum": page_num,
        "pageSize": page_size,
        "total": total,
    }
    return make_response(200, data=data, msg="success")


@geeker_router.post("/user/add", dependencies=[Depends(require_permission("user:add"))])
@api_router.post("/user/add", dependencies=[Depends(require_permission("user:add"))])
def user_add(
    body: UserAddBody,
    db: Session = Depends(get_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    name = body.username.strip()
    if db.query(SysUser).filter(SysUser.username == name).first():
        return make_response(500, data={}, msg="用户名已存在")

    gv = (str(body.gender).strip() if body.gender is not None else "") or "3"
    u = SysUser(
        username=name,
        password=pwd_context.hash(body.password),
        nickname=body.nickname,
        email=body.email,
        phone=body.phone,
        gender=gv,
        is_active=True,
        is_superuser=False,
    )
    if body.roleIds:
        roles = db.query(SysRole).filter(SysRole.id.in_(body.roleIds), SysRole.is_active == True).all()  # noqa: E712
        u.roles = roles
    db.add(u)
    db.commit()
    return make_response(200, data={}, msg="新增成功")


@geeker_router.post("/user/delete", dependencies=[Depends(require_permission("user:delete"))])
@api_router.post("/user/delete", dependencies=[Depends(require_permission("user:delete"))])
def user_delete(
    body: UserDeleteBody,
    db: Session = Depends(get_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    current_uid = ctx["user_id"]
    deleted = 0
    for raw in body.id:
        uid = int(raw) if not isinstance(raw, int) else raw
        if uid == current_uid:
            return make_response(500, data={}, msg="不能删除当前登录用户")
        u = db.query(SysUser).filter(SysUser.id == uid).first()
        if u:
            db.delete(u)
            deleted += 1
    if not deleted:
        return make_response(500, data={}, msg="用户不存在或已删除")

    db.commit()
    return make_response(200, data={}, msg="删除成功")


@geeker_router.post("/user/edit", dependencies=[Depends(require_permission("user:edit"))])
@api_router.post("/user/edit", dependencies=[Depends(require_permission("user:edit"))])
def user_edit(
    body: UserEditBody,
    db: Session = Depends(get_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    uid = int(body.id) if not isinstance(body.id, int) else body.id
    u = db.query(SysUser).filter(SysUser.id == uid).first()
    if not u:
        return make_response(500, data={}, msg="用户不存在")

    if body.username is not None:
        name = body.username.strip()
        if not name:
            return make_response(500, data={}, msg="用户名不能为空")
        if name != u.username:
            other = db.query(SysUser).filter(SysUser.username == name, SysUser.id != uid).first()
            if other:
                return make_response(500, data={}, msg="用户名已存在")
            u.username = name

    if body.nickname is not None:
        u.nickname = body.nickname
    if body.email is not None:
        u.email = body.email
    if body.phone is not None:
        u.phone = body.phone
    if body.gender is not None:
        u.gender = str(body.gender).strip() or "3"
    role_ids = list(dict.fromkeys([int(rid) for rid in (body.roleIds or [])]))
    if role_ids:
        roles = db.query(SysRole).filter(SysRole.id.in_(role_ids), SysRole.is_active == True).all()  # noqa: E712
        u.roles = roles
    else:
        u.roles = []

    db.commit()
    return make_response(200, data={}, msg="编辑成功")


@geeker_router.post("/user/changeStatus")
@api_router.post("/user/changeStatus")
def user_change_status(
    body: UserChangeStatusBody,
    db: Session = Depends(get_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    if body.status not in (0, 1):
        return make_response(500, data={}, msg="状态参数无效")

    uid = int(body.id) if not isinstance(body.id, int) else body.id
    current_uid = ctx["user_id"]

    if uid == current_uid and body.status == 0:
        return make_response(500, data={}, msg="不能禁用当前登录用户")

    u = db.query(SysUser).filter(SysUser.id == uid).first()
    if not u:
        return make_response(500, data={}, msg="用户不存在")

    u.is_active = bool(body.status)
    db.commit()
    return make_response(200, data={}, msg="状态修改成功")


def _role_row(r: SysRole) -> Dict[str, Any]:
    created = r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else ""
    return {
        "id": str(r.id),
        "roleName": r.name,
        "roleCode": r.code,
        "remark": r.description or "",
        "status": 1 if r.is_active else 0,
        "createTime": created,
    }


@geeker_router.post("/role/list")
@api_router.post("/role/list")
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
        "list": [_role_row(r) for r in rows],
        "pageNum": page_num,
        "pageSize": page_size,
        "total": total,
    }
    return make_response(200, data=data, msg="success")


@geeker_router.get("/role/all")
@api_router.get("/role/all")
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


@geeker_router.post("/role/add")
@api_router.post("/role/add")
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


@geeker_router.post("/role/edit")
@api_router.post("/role/edit")
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


@geeker_router.post("/role/delete")
@api_router.post("/role/delete")
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
        db.delete(role)
        deleted += 1

    if not deleted:
        return make_response(500, data={}, msg="角色不存在或已删除")

    db.commit()
    return make_response(200, data={}, msg="删除成功")


def _query_menu_tree_for_manage(db: Session) -> List[dict]:
    """菜单管理：返回全部菜单（含停用）树。"""
    rows = (
        db.query(SysMenu)
        .order_by(SysMenu.sort.asc(), SysMenu.id.asc())
        .all()
    )
    return build_menu_tree_all(rows)


@geeker_router.get("/menu/all_tree")
@api_router.get("/menu/all_tree")
def menu_all_tree(
    db: Session = Depends(get_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = require_user(x_access_token)
    if not ctx:
        return make_response(401, data=[], msg="登录过期，请重新登录")

    rows = (
        db.query(SysMenu)
        .filter(SysMenu.status == True)  # noqa: E712
        .order_by(SysMenu.sort.asc(), SysMenu.id.asc())
        .all()
    )
    tree = build_menu_tree_all(rows)
    return make_response(200, data=tree, msg="success")


@geeker_router.get("/menu/manage_tree")
@api_router.get("/menu/manage_tree")
def menu_manage_tree(
    db: Session = Depends(get_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    """菜单管理页数据源：全量树（含停用）。"""
    ctx = require_user(x_access_token)
    if not ctx:
        return make_response(401, data=[], msg="登录过期，请重新登录")
    return make_response(200, data=_query_menu_tree_for_manage(db), msg="success")


@geeker_router.post("/role/getMenuIds")
@api_router.post("/role/getMenuIds")
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


@geeker_router.post("/role/assignMenu")
@api_router.post("/role/assignMenu")
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

    return make_response(200, data={}, msg="权限分配成功")


@geeker_router.post("/menu/add")
@api_router.post("/menu/add")
def menu_add(
    body: MenuAddBody,
    db: Session = Depends(get_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    mt = (body.menuType or "MENU").strip().upper()
    if mt not in _MENU_TYPES:
        return make_response(500, data={}, msg="菜单类型无效")

    pid = body.parentId
    if pid is not None:
        parent = db.query(SysMenu).filter(SysMenu.id == pid).first()
        if not parent:
            return make_response(500, data={}, msg="父级菜单不存在")

    m = SysMenu(
        parent_id=pid,
        menu_type=mt,
        name=body.name.strip(),
        title=body.title.strip(),
        path=(body.path or "").strip() or None,
        component=(body.component or "").strip() or None,
        icon=(body.icon or "").strip() or None,
        sort=body.sort,
        remark=body.remark,
        status=True,
    )
    db.add(m)
    db.commit()
    return make_response(200, data={}, msg="新增成功")


@geeker_router.post("/menu/edit")
@api_router.post("/menu/edit")
def menu_edit(
    body: MenuEditBody,
    db: Session = Depends(get_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    mid = int(body.id) if not isinstance(body.id, int) else body.id
    m = db.query(SysMenu).filter(SysMenu.id == mid).first()
    if not m:
        return make_response(500, data={}, msg="菜单不存在")

    if body.parentId is not None:
        if body.parentId == mid:
            return make_response(500, data={}, msg="不能将父级设为自身")
        if body.parentId == 0:
            m.parent_id = None
        else:
            parent = db.query(SysMenu).filter(SysMenu.id == body.parentId).first()
            if not parent:
                return make_response(500, data={}, msg="父级菜单不存在")
            m.parent_id = body.parentId

    if body.menuType is not None:
        mt = body.menuType.strip().upper()
        if mt not in _MENU_TYPES:
            return make_response(500, data={}, msg="菜单类型无效")
        m.menu_type = mt
    if body.name is not None:
        m.name = body.name.strip()
    if body.title is not None:
        m.title = body.title.strip()
    if body.path is not None:
        m.path = body.path.strip() or None
    if body.component is not None:
        m.component = body.component.strip() or None
    if body.icon is not None:
        m.icon = body.icon.strip() or None
    if body.sort is not None:
        m.sort = body.sort
    if body.remark is not None:
        m.remark = body.remark
    if body.status is not None:
        m.status = body.status

    db.commit()
    return make_response(200, data={}, msg="编辑成功")


@geeker_router.post("/menu/delete")
@api_router.post("/menu/delete")
def menu_delete(
    body: MenuDeleteBody,
    db: Session = Depends(get_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    mid = int(body.id) if not isinstance(body.id, int) else body.id
    m = db.query(SysMenu).filter(SysMenu.id == mid).first()
    if not m:
        return make_response(500, data={}, msg="菜单不存在")

    has_child = db.query(SysMenu).filter(SysMenu.parent_id == mid).first()
    if has_child:
        return make_response(500, data={}, msg="请先删除子菜单")

    db.delete(m)
    db.commit()
    return make_response(200, data={}, msg="删除成功")


@geeker_router.get("/biz/home/statistics")
@api_router.get("/biz/home/statistics")
def biz_home_statistics(
    db: Session = Depends(get_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    def load() -> Dict[str, Any]:
        return _compute_home_statistics(db)

    data = cache_get_or_set_json("home:stats", 300, load)
    return make_response(200, data=data, msg="success")


@geeker_router.post("/biz/newsCategory/list")
@api_router.post("/biz/newsCategory/list")
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
            "list": [_news_category_row(r) for r in rows],
            "pageNum": body.pageNum,
            "pageSize": body.pageSize,
            "total": total,
        },
        msg="success",
    )


@geeker_router.post("/biz/newsCategory/add", dependencies=[Depends(require_permission("newsCategory:add"))])
@api_router.post("/biz/newsCategory/add", dependencies=[Depends(require_permission("newsCategory:add"))])
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


@geeker_router.post("/biz/newsCategory/edit", dependencies=[Depends(require_permission("newsCategory:edit"))])
@api_router.post("/biz/newsCategory/edit", dependencies=[Depends(require_permission("newsCategory:edit"))])
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


@geeker_router.post("/biz/newsCategory/delete", dependencies=[Depends(require_permission("newsCategory:delete"))])
@api_router.post("/biz/newsCategory/delete", dependencies=[Depends(require_permission("newsCategory:delete"))])
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


@geeker_router.post("/biz/newsCategory/changeStatus", dependencies=[Depends(require_permission("newsCategory:edit"))])
@api_router.post("/biz/newsCategory/changeStatus", dependencies=[Depends(require_permission("newsCategory:edit"))])
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


@geeker_router.get("/biz/newsCategory/all")
@api_router.get("/biz/newsCategory/all")
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


@geeker_router.post("/biz/newsArticle/list")
@api_router.post("/biz/newsArticle/list")
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
    data_list = [_news_article_row(r, category_map.get(str(r.category_id), "")) for r in rows]
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


@geeker_router.post("/biz/newsArticle/add", dependencies=[Depends(require_permission("newsArticle:add"))])
@api_router.post("/biz/newsArticle/add", dependencies=[Depends(require_permission("newsArticle:add"))])
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


@geeker_router.post("/biz/newsArticle/edit", dependencies=[Depends(require_permission("newsArticle:edit"))])
@api_router.post("/biz/newsArticle/edit", dependencies=[Depends(require_permission("newsArticle:edit"))])
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


@geeker_router.post("/biz/newsArticle/delete", dependencies=[Depends(require_permission("newsArticle:delete"))])
@api_router.post("/biz/newsArticle/delete", dependencies=[Depends(require_permission("newsArticle:delete"))])
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


@geeker_router.post("/biz/newsArticle/changeStatus", dependencies=[Depends(require_permission("newsArticle:edit"))])
@api_router.post("/biz/newsArticle/changeStatus", dependencies=[Depends(require_permission("newsArticle:edit"))])
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


@geeker_router.post("/biz/fragment/category/list")
@api_router.post("/biz/fragment/category/list")
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
            "list": [_fragment_category_row(r) for r in rows],
            "pageNum": body.pageNum,
            "pageSize": body.pageSize,
            "total": total,
        },
        msg="success",
    )


@geeker_router.post("/biz/fragment/category/add", dependencies=[Depends(require_permission("fragmentCategory:add"))])
@api_router.post("/biz/fragment/category/add", dependencies=[Depends(require_permission("fragmentCategory:add"))])
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


@geeker_router.post("/biz/fragment/category/edit", dependencies=[Depends(require_permission("fragmentCategory:edit"))])
@api_router.post("/biz/fragment/category/edit", dependencies=[Depends(require_permission("fragmentCategory:edit"))])
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


@geeker_router.post("/biz/fragment/category/delete", dependencies=[Depends(require_permission("fragmentCategory:delete"))])
@api_router.post("/biz/fragment/category/delete", dependencies=[Depends(require_permission("fragmentCategory:delete"))])
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


@geeker_router.post("/biz/fragment/content/list")
@api_router.post("/biz/fragment/content/list")
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
            "list": [_fragment_content_row(r) for r in rows],
            "pageNum": body.pageNum,
            "pageSize": body.pageSize,
            "total": total,
        },
        msg="success",
    )


@geeker_router.post("/biz/fragment/content/add", dependencies=[Depends(require_permission("fragmentContent:add"))])
@api_router.post("/biz/fragment/content/add", dependencies=[Depends(require_permission("fragmentContent:add"))])
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


@geeker_router.post("/biz/fragment/content/edit", dependencies=[Depends(require_permission("fragmentContent:edit"))])
@api_router.post("/biz/fragment/content/edit", dependencies=[Depends(require_permission("fragmentContent:edit"))])
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


@geeker_router.post("/biz/fragment/content/delete", dependencies=[Depends(require_permission("fragmentContent:delete"))])
@api_router.post("/biz/fragment/content/delete", dependencies=[Depends(require_permission("fragmentContent:delete"))])
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


@geeker_router.post("/biz/fragment/content/changeStatus", dependencies=[Depends(require_permission("fragmentContent:edit"))])
@api_router.post("/biz/fragment/content/changeStatus", dependencies=[Depends(require_permission("fragmentContent:edit"))])
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


@geeker_router.post("/sys/log/list")
@api_router.post("/sys/log/list")
def sys_oper_log_list(
    body: SysOperLogListBody,
    db: Session = Depends(get_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    q = db.query(SysOperLog)
    if body.userName and body.userName.strip():
        q = q.filter(SysOperLog.user_name.like(f"%{body.userName.strip()}%"))
    if body.requestMethod and body.requestMethod.strip():
        q = q.filter(SysOperLog.request_method == body.requestMethod.strip().upper())

    total = q.count()
    rows = (
        q.order_by(SysOperLog.create_time.desc())
        .offset((body.pageNum - 1) * body.pageSize)
        .limit(body.pageSize)
        .all()
    )
    return make_response(
        200,
        data={
            "list": [_oper_log_row(r) for r in rows],
            "pageNum": body.pageNum,
            "pageSize": body.pageSize,
            "total": total,
        },
        msg="success",
    )


@geeker_router.post("/file/upload")
@geeker_router.post("/file/upload/img")
@api_router.post("/file/upload")
@api_router.post("/file/upload/img")
async def file_upload(
    request: Request,
    file: UploadFile = File(...),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    orig = (file.filename or "file").strip()
    suffix = Path(orig).suffix
    if suffix:
        suffix = suffix.lower()
    else:
        suffix = ""
    new_name = f"{uuid.uuid4().hex}{suffix}"
    dest = UPLOAD_DIR / new_name
    try:
        with dest.open("wb") as out:
            shutil.copyfileobj(file.file, out)
    finally:
        await file.close()

    base = str(request.base_url).rstrip("/")
    file_url = f"{base}/uploads/{new_name}"
    return make_response(200, data={"fileUrl": file_url}, msg="上传成功")


app = FastAPI(title="Geeker-Admin FastAPI Auth Center")


def _validation_error_message(exc: RequestValidationError) -> str:
    parts: List[str] = []
    for err in exc.errors()[:12]:
        loc = err.get("loc") or ()
        loc_s = ".".join(str(x) for x in loc if x != "body")
        msg = err.get("msg", "")
        if loc_s:
            parts.append(f"{loc_s}: {msg}")
        else:
            parts.append(str(msg))
    return "; ".join(parts) if parts else "请求参数不合法"


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    detail = _validation_error_message(exc)
    return JSONResponse(
        status_code=200,
        content={"code": 400, "msg": f"参数校验失败: {detail}", "data": None},
        headers={"X-Geeker-Code": "400"},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    msg = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    return JSONResponse(
        status_code=200,
        content={"code": exc.status_code, "msg": msg, "data": None},
        headers={"X-Geeker-Code": str(exc.status_code)},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    traceback.print_exc()
    logger.error("未捕获异常: %s", exc, exc_info=(type(exc), exc, exc.__traceback__))
    return JSONResponse(
        status_code=200,
        content={"code": 500, "msg": "系统开小差了，请稍后再试", "data": None},
        headers={"X-Geeker-Code": "500"},
    )


@app.middleware("http")
async def oper_log_middleware(request: Request, call_next):
    method = request.method.upper()
    if method in ("GET", "HEAD", "OPTIONS"):
        return await call_next(request)

    path = request.url.path
    if path.startswith("/docs") or path in ("/openapi.json", "/redoc") or path.startswith("/redoc"):
        return await call_next(request)

    access_token = request.headers.get("x-access-token")
    ip = _client_ip(request)
    url = path[:512]

    request_param_str: Optional[str] = None
    ct = (request.headers.get("content-type") or "").lower()
    if "multipart/form-data" in ct:
        request_param_str = "[multipart/form-data，未记录正文]"
    else:
        body_bytes = await request.body()
        if body_bytes:
            try:
                request_param_str = body_bytes.decode("utf-8")[:2000]
            except UnicodeDecodeError:
                request_param_str = body_bytes.decode("utf-8", errors="replace")[:2000]
        async def receive():
            return {"type": "http.request", "body": body_bytes}

        request._receive = receive  # type: ignore[method-assign]

    start = time.perf_counter()
    caught: Optional[Exception] = None
    response: Optional[Response] = None
    try:
        response = await call_next(request)
        return response
    except Exception as e:
        caught = e
        raise
    finally:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        status_val, err_msg = _resolve_oper_log_status(response, caught)
        asyncio.create_task(
            _flush_oper_log_background(
                access_token,
                method,
                url,
                ip,
                elapsed_ms,
                status_val,
                err_msg,
                request_param_str,
            )
        )


app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=_settings.cors_allow_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(geeker_router)
app.include_router(api_router)
