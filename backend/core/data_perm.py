"""
数据权限：在 SQLAlchemy 2.0 的 select 语句上按上下文拼接 WHERE 条件。
"""

from __future__ import annotations

from typing import Any, Type

from sqlalchemy import false
from sqlalchemy.sql import Select

from core.context import (
    ctx_allowed_dept_ids,
    ctx_data_scope,
    ctx_is_superuser,
    ctx_user_id,
)
from models.rbac import DataScopeEnum


def _table_has_columns(model: Type[Any], *names: str) -> bool:
    tbl = getattr(model, "__table__", None)
    if tbl is None:
        return False
    return all(n in tbl.c for n in names)


def apply_data_scope(stmt: Select[Any], model: Type[Any]) -> Select[Any]:
    """
    按 contextvars 中的数据权限为 ``stmt`` 追加条件。

    要求受控业务模型具备 ``dept_id``、``created_by`` 字段（与项目规范一致）。
    若未注入数据权限上下文（``ctx_data_scope`` 为 None），则不做修改（兼容未接入的接口）。
    """
    if ctx_is_superuser.get() is True:
        return stmt

    scope = ctx_data_scope.get()
    if scope is None:
        return stmt

    if scope == DataScopeEnum.ALL.value:
        return stmt

    has_dept = _table_has_columns(model, "dept_id")
    has_creator = _table_has_columns(model, "created_by")
    if not has_dept and not has_creator:
        return stmt

    if scope in (
        DataScopeEnum.DEPT_AND_CHILD.value,
        DataScopeEnum.DEPT_ONLY.value,
        DataScopeEnum.CUSTOM_DEPTS.value,
    ):
        if not has_dept:
            return stmt.where(false())
        raw = ctx_allowed_dept_ids.get() or []
        ids = list(dict.fromkeys(raw))
        if not ids:
            return stmt.where(false())
        return stmt.where(model.dept_id.in_(ids))

    if scope == DataScopeEnum.SELF_ONLY.value:
        if not has_creator:
            return stmt.where(false())
        uid = ctx_user_id.get()
        if uid is None:
            return stmt.where(false())
        return stmt.where(model.created_by == uid)

    return stmt
