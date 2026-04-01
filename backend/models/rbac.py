from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base


class SysUserRole(Base):
    """
    用户-角色关联表（多对多）
    """

    __tablename__ = "sys_user_role"
    __table_args__ = (UniqueConstraint("user_id", "role_id", name="uq_sys_user_role_user_role"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("sys_user.id", ondelete="CASCADE"), nullable=False, index=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("sys_role.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class SysRoleMenu(Base):
    """
    角色-菜单关联表（多对多）
    """

    __tablename__ = "sys_role_menu"
    __table_args__ = (UniqueConstraint("role_id", "menu_id", name="uq_sys_role_menu_role_menu"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("sys_role.id", ondelete="CASCADE"), nullable=False, index=True)
    menu_id: Mapped[int] = mapped_column(ForeignKey("sys_menu.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class SysUser(Base):
    """
    用户表
    """

    __tablename__ = "sys_user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    password: Mapped[str] = mapped_column(String(128), nullable=False, comment="建议保存加盐哈希")
    nickname: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    avatar: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    gender: Mapped[str] = mapped_column(String(8), default="3", nullable=False, comment="字典 sys_user_sex：1男 2女 3未知")
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # 用户 <-> 角色（多对多）
    roles: Mapped[List["SysRole"]] = relationship(
        secondary="sys_user_role",
        back_populates="users",
        lazy="selectin",
    )


class SysRole(Base):
    """
    角色表
    """

    __tablename__ = "sys_role"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True, comment="例如 admin/editor")
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # 角色 <-> 用户（多对多）
    users: Mapped[List[SysUser]] = relationship(
        secondary="sys_user_role",
        back_populates="roles",
        lazy="selectin",
    )

    # 角色 <-> 菜单（多对多）
    menus: Mapped[List["SysMenu"]] = relationship(
        secondary="sys_role_menu",
        back_populates="roles",
        lazy="selectin",
    )


class SysMenu(Base):
    """
    菜单/权限表（支持目录、菜单、按钮）
    """

    __tablename__ = "sys_menu"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    parent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("sys_menu.id", ondelete="SET NULL"), nullable=True, index=True)
    menu_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="MENU",
        comment="目录:CATALOG 菜单:MENU 按钮:BUTTON",
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False, comment="路由 name 或按钮标识")
    title: Mapped[str] = mapped_column(String(64), nullable=False, comment="显示名称")
    path: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="前端路由 path")
    component: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="前端组件路径")
    icon: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    permission: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True, comment="如 system:user:add")
    sort: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_link: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="外链地址")
    is_hide: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_full: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_affix: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_keep_alive: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    remark: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # 自关联：父子菜单
    parent: Mapped[Optional["SysMenu"]] = relationship(
        remote_side="SysMenu.id",
        back_populates="children",
        lazy="selectin",
    )
    children: Mapped[List["SysMenu"]] = relationship(
        back_populates="parent",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # 菜单 <-> 角色（多对多）
    roles: Mapped[List[SysRole]] = relationship(
        secondary="sys_role_menu",
        back_populates="menus",
        lazy="selectin",
    )

