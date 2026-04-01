from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class SysDictType(Base):
    """字典类型表"""

    __tablename__ = "sys_dict_type"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dict_name: Mapped[str] = mapped_column(String(128), nullable=False, comment="字典名称")
    dict_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True, comment="字典编码")
    status: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    remark: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class SysDictData(Base):
    """字典数据表"""

    __tablename__ = "sys_dict_data"
    __table_args__ = (UniqueConstraint("dict_code", "dict_value", name="uq_sys_dict_data_code_value"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dict_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True, comment="关联字典类型编码")
    dict_label: Mapped[str] = mapped_column(String(128), nullable=False, comment="展示标签")
    dict_value: Mapped[str] = mapped_column(String(128), nullable=False, comment="存储值")
    sort: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    remark: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
