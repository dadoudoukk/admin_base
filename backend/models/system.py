from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base
from models.base import SoftDeleteMixin


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
