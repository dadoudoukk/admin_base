from datetime import datetime

from sqlalchemy import DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column


class SoftDeleteMixin:
    is_delete: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="是否删除 0-否 1-是")
    delete_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="删除时间")
