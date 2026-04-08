from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base
from models.base import SoftDeleteMixin


class SysDept(SoftDeleteMixin, Base):
    """部门表（树形，parent_id 指向父部门）。"""

    __tablename__ = "sys_dept"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    parent_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("sys_dept.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="父部门 ID，根部门为 NULL",
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False, comment="部门名称")
    sort: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="排序")
    status: Mapped[int] = mapped_column(Integer, default=1, nullable=False, comment="0停用 1正常")
    remark: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="备注")
    create_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    parent: Mapped[Optional["SysDept"]] = relationship(
        remote_side="SysDept.id",
        back_populates="children",
    )
    children: Mapped[List["SysDept"]] = relationship(
        back_populates="parent",
    )


class SysOperLog(SoftDeleteMixin, Base):
    """系统操作日志"""

    __tablename__ = "sys_oper_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True, comment="操作人账号")
    request_method: Mapped[str] = mapped_column(String(16), nullable=False, index=True, comment="HTTP 方法")
    request_url: Mapped[str] = mapped_column(String(512), nullable=False, comment="请求路径")
    request_ip: Mapped[str] = mapped_column(String(64), nullable=False, default="", comment="客户端 IP")
    execute_time: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="执行耗时（毫秒）")
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment="0失败 1成功")
    error_msg: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="错误信息")
    request_param: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="请求参数")
    create_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, comment="记录时间")
