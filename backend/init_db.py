"""
一次性初始化脚本：向 MySQL 写入首套 RBAC 基础测试数据。

用法（在 backend 目录下）:
    python init_db.py

也可在项目根目录:
    python backend/init_db.py

数据库连接使用 core.database 中的 DATABASE_URL，请按需修改该文件。
"""
from __future__ import annotations

import sys
from pathlib import Path

# 保证从任意工作目录运行都能导入 backend 包
_BACKEND_ROOT = Path(__file__).resolve().parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from passlib.context import CryptContext
from sqlalchemy.orm import Session

# 导入模型，确保 metadata 完整
from models import BizNewsArticle, BizNewsCategory, SysDictData, SysDictType, SysMenu, SysRole, SysUser  # noqa: F401

from core.database import Base, SessionLocal, engine

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def ensure_tables() -> None:
    Base.metadata.create_all(bind=engine)


def ensure_biz_news_article_cover_image_column() -> None:
    """旧库无 cover_image_url 列时执行 ALTER。"""
    from sqlalchemy import inspect, text

    try:
        insp = inspect(engine)
        cols = [c["name"] for c in insp.get_columns("biz_news_article")]
    except Exception:
        return
    if "cover_image_url" in cols:
        return
    with engine.begin() as conn:
        conn.execute(
            text(
                "ALTER TABLE biz_news_article ADD COLUMN cover_image_url VARCHAR(512) NULL COMMENT '封面图 URL'"
            )
        )
    print("已为 biz_news_article 表补充 cover_image_url 字段（旧库升级）。")


def ensure_user_gender_column() -> None:
    """旧库无 gender 列时执行 ALTER，避免仅依赖 create_all 无法加列。"""
    from sqlalchemy import inspect, text

    try:
        insp = inspect(engine)
        cols = [c["name"] for c in insp.get_columns("sys_user")]
    except Exception:
        return
    if "gender" in cols:
        return
    with engine.begin() as conn:
        conn.execute(
            text(
                "ALTER TABLE sys_user ADD COLUMN gender VARCHAR(8) NOT NULL DEFAULT '3' "
                "COMMENT '字典 sys_user_sex'"
            )
        )
    print("已为 sys_user 表补充 gender 字段（旧库升级）。")


def seed(session: Session) -> None:
    if session.query(SysUser).filter(SysUser.username == "admin").first():
        print("已存在用户 admin，跳过写入（避免重复）。")
        return

    menu_home = SysMenu(
        parent_id=None,
        menu_type="MENU",
        name="home_index",
        title="首页",
        path="/home/index",
        sort=1,
    )
    menu_system = SysMenu(
        parent_id=None,
        menu_type="CATALOG",
        name="system",
        title="系统管理",
        path="/system",
        sort=2,
    )
    session.add_all([menu_home, menu_system])
    session.flush()

    role = SysRole(
        name="超级管理员",
        code="admin",
        description="系统内置超级管理员",
    )
    role.menus = [menu_home, menu_system]
    session.add(role)
    session.flush()

    user = SysUser(
        username="admin",
        password=pwd_context.hash("123456"),
        nickname="管理员",
        gender="3",
        is_superuser=True,
        is_active=True,
    )
    user.roles = [role]
    session.add(user)

    session.commit()
    print("初始化完成：已写入「首页」「系统管理」菜单、超级管理员角色、admin 用户（明文密码 123456）。")


def ensure_user_manage_menu(session: Session) -> None:
    """
    在「系统管理」下挂「用户管理」菜单并授权给 admin 角色；可重复执行（已存在则跳过）。
    """
    parent = session.query(SysMenu).filter(SysMenu.name == "system").first()
    if not parent:
        print("未找到「系统管理」菜单，跳过用户管理菜单补充。")
        return
    if session.query(SysMenu).filter(SysMenu.name == "accountManage").first():
        return

    child = SysMenu(
        parent_id=parent.id,
        menu_type="MENU",
        name="accountManage",
        title="用户管理",
        path="/system/accountManage",
        component="/system/accountManage/index",
        icon="User",
        sort=1,
    )
    session.add(child)
    session.flush()

    role = session.query(SysRole).filter(SysRole.code == "admin").first()
    if role and child not in role.menus:
        role.menus.append(child)

    session.commit()
    print("已补充「系统管理 -> 用户管理」菜单并关联超级管理员角色。")


def ensure_role_manage_menu(session: Session) -> None:
    """在「系统管理」下挂「角色管理」菜单并授权给 admin；已存在则跳过。"""
    parent = session.query(SysMenu).filter(SysMenu.name == "system").first()
    if not parent:
        print("未找到「系统管理」菜单，跳过角色管理菜单补充。")
        return
    if session.query(SysMenu).filter(SysMenu.name == "roleManage").first():
        return

    child = SysMenu(
        parent_id=parent.id,
        menu_type="MENU",
        name="roleManage",
        title="角色管理",
        path="/system/roleManage",
        component="/system/roleManage/index",
        icon="UserFilled",
        sort=2,
    )
    session.add(child)
    session.flush()

    role = session.query(SysRole).filter(SysRole.code == "admin").first()
    if role and child not in role.menus:
        role.menus.append(child)

    session.commit()
    print("已补充「系统管理 -> 角色管理」菜单并关联超级管理员角色。")


def ensure_menu_manage_menu(session: Session) -> None:
    """在「系统管理」下挂「菜单管理」并授权 admin；已存在则跳过。"""
    parent = session.query(SysMenu).filter(SysMenu.name == "system").first()
    if not parent:
        print("未找到「系统管理」菜单，跳过菜单管理补充。")
        return
    if session.query(SysMenu).filter(SysMenu.name == "menuManage").first():
        return

    child = SysMenu(
        parent_id=parent.id,
        menu_type="MENU",
        name="menuManage",
        title="菜单管理",
        path="/system/menuMange",
        component="/system/menuMange/index",
        icon="Menu",
        sort=3,
    )
    session.add(child)
    session.flush()

    role = session.query(SysRole).filter(SysRole.code == "admin").first()
    if role and child not in role.menus:
        role.menus.append(child)

    session.commit()
    print("已补充「系统管理 -> 菜单管理」菜单并关联超级管理员角色。")


def ensure_dict_manage_menu(session: Session) -> None:
    """在「系统管理」下挂「字典管理」并授权 admin；已存在则跳过。"""
    parent = session.query(SysMenu).filter(SysMenu.name == "system").first()
    if not parent:
        print("未找到「系统管理」菜单，跳过字典管理补充。")
        return
    if session.query(SysMenu).filter(SysMenu.name == "dictManage").first():
        return

    child = SysMenu(
        parent_id=parent.id,
        menu_type="MENU",
        name="dictManage",
        title="字典管理",
        path="/system/dictManage",
        component="/system/dictManage/index",
        icon="Memo",
        sort=4,
    )
    session.add(child)
    session.flush()

    role = session.query(SysRole).filter(SysRole.code == "admin").first()
    if role and child not in role.menus:
        role.menus.append(child)

    session.commit()
    print("已补充「系统管理 -> 字典管理」菜单并关联超级管理员角色。")


def ensure_sys_dict_init(session: Session) -> None:
    """
    写入数据字典「用户性别」测试数据；已存在类型或同编码取值则跳过（可重复执行）。
    """
    code = "sys_user_sex"
    if not session.query(SysDictType).filter(SysDictType.dict_code == code).first():
        session.add(
            SysDictType(
                dict_name="用户性别",
                dict_code=code,
                status=True,
                remark=None,
            )
        )

    items = (
        ("男", "1", 1),
        ("女", "2", 2),
        ("未知", "3", 3),
    )
    for label, value, sort in items:
        exists = (
            session.query(SysDictData)
            .filter(SysDictData.dict_code == code, SysDictData.dict_value == value)
            .first()
        )
        if exists:
            continue
        session.add(
            SysDictData(
                dict_code=code,
                dict_label=label,
                dict_value=value,
                sort=sort,
                status=True,
                remark=None,
            )
        )

    session.commit()
    print("数据字典 sys_user_sex 已检查并写入（无重复项则跳过）。")


def ensure_news_center_menu(session: Session) -> None:
    """创建「新闻中心 -> 新闻分类」菜单并授权 admin；已存在则跳过。"""
    parent = session.query(SysMenu).filter(SysMenu.name == "newsCenter").first()
    if not parent:
        parent = SysMenu(
            parent_id=None,
            menu_type="CATALOG",
            name="newsCenter",
            title="新闻中心",
            path="/news",
            icon="Document",
            sort=3,
        )
        session.add(parent)
        session.flush()

    child = session.query(SysMenu).filter(SysMenu.name == "newsCategory").first()
    if not child:
        child = SysMenu(
            parent_id=parent.id,
            menu_type="MENU",
            name="newsCategory",
            title="新闻分类",
            path="/news/newsCategory",
            component="/news/newsCategory/index",
            icon="Menu",
            sort=1,
        )
        session.add(child)
        session.flush()

    role = session.query(SysRole).filter(SysRole.code == "admin").first()
    if role:
        if parent not in role.menus:
            role.menus.append(parent)
        if child not in role.menus:
            role.menus.append(child)

    session.commit()
    print("已检查「新闻中心 -> 新闻分类」菜单并关联超级管理员角色。")


def ensure_news_category_init(session: Session) -> None:
    """写入新闻分类初始化数据；已存在同名分类则跳过。"""
    items = [
        ("公司动态", 1),
        ("行业资讯", 2),
        ("通知公告", 3),
    ]
    for name, sort in items:
        exists = session.query(BizNewsCategory).filter(BizNewsCategory.category_name == name).first()
        if exists:
            continue
        session.add(
            BizNewsCategory(
                category_name=name,
                sort=sort,
                status=1,
                remark=None,
            )
        )
    session.commit()
    print("新闻分类初始化数据已检查并写入（无重复项则跳过）。")


def ensure_news_article_menu(session: Session) -> None:
    """在「新闻中心」下挂「新闻列表」菜单并授权 admin。"""
    parent = session.query(SysMenu).filter(SysMenu.name == "newsCenter").first()
    if not parent:
        print("未找到「新闻中心」菜单，跳过新闻列表菜单补充。")
        return
    child = session.query(SysMenu).filter(SysMenu.name == "newsArticle").first()
    if not child:
        child = SysMenu(
            parent_id=parent.id,
            menu_type="MENU",
            name="newsArticle",
            title="新闻列表",
            path="/news/newsArticle",
            component="/news/newsArticle/index",
            icon="Document",
            sort=2,
        )
        session.add(child)
        session.flush()

    role = session.query(SysRole).filter(SysRole.code == "admin").first()
    if role and child not in role.menus:
        role.menus.append(child)
    session.commit()
    print("已检查「新闻中心 -> 新闻列表」菜单并关联超级管理员角色。")


def ensure_news_article_init(session: Session) -> None:
    """写入一条新闻文章测试数据（挂公司动态分类）。"""
    category = session.query(BizNewsCategory).filter(BizNewsCategory.category_name == "公司动态").first()
    if not category:
        print("未找到「公司动态」分类，跳过新闻文章初始化数据。")
        return

    exists = session.query(BizNewsArticle).filter(BizNewsArticle.title == "欢迎使用新闻中心").first()
    if exists:
        print("新闻文章测试数据已存在，跳过写入。")
        return

    session.add(
        BizNewsArticle(
            category_id=category.id,
            title="欢迎使用新闻中心",
            author="admin",
            news_type=0,
            content="这是一条初始化新闻，用于验证新闻列表基础功能。",
            redirect_url=None,
            is_top=1,
            status=1,
        )
    )
    session.commit()
    print("新闻文章初始化数据已写入。")


def main() -> None:
    ensure_tables()
    ensure_user_gender_column()
    ensure_biz_news_article_cover_image_column()
    session = SessionLocal()
    try:
        seed(session)
        ensure_user_manage_menu(session)
        ensure_role_manage_menu(session)
        ensure_menu_manage_menu(session)
        ensure_dict_manage_menu(session)
        ensure_sys_dict_init(session)
        ensure_news_center_menu(session)
        ensure_news_category_init(session)
        ensure_news_article_menu(session)
        ensure_news_article_init(session)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
