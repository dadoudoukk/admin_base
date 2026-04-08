"""
请求级数据权限上下文（contextvars）。

在持有请求级 Session 的依赖/路由中调用 `activate_data_permission_context`，
随后在 Service/Repository 中通过 `apply_data_scope` 读取这些变量。
请求结束后应由中间件调用 `clear_data_permission_context`，避免同线程复用时串上下文。
"""

from __future__ import annotations

from contextvars import ContextVar, Token
from typing import List, Optional

# 当前登录用户 ID（sys_user.id）
ctx_user_id: ContextVar[Optional[int]] = ContextVar("ctx_user_id", default=None)

# 当前用户所属部门 ID（sys_dept.id），未分配则为 None
ctx_dept_id: ContextVar[Optional[int]] = ContextVar("ctx_dept_id", default=None)

# 合并后的有效数据范围（见 models.rbac.DataScopeEnum）
ctx_data_scope: ContextVar[Optional[int]] = ContextVar("ctx_data_scope", default=None)

# 权限预处理后可访问的部门集合（去重后的 list[int]）
ctx_allowed_dept_ids: ContextVar[Optional[List[int]]] = ContextVar("ctx_allowed_dept_ids", default=None)

ctx_is_superuser: ContextVar[Optional[bool]] = ContextVar("ctx_is_superuser", default=None)

ContextTokens = dict[str, Token[object]]


def begin_data_permission_context_scope() -> ContextTokens:
    """
    以 token 方式初始化请求级上下文，返回 token 映射，供 finally reset。
    """
    return {
        "ctx_user_id": ctx_user_id.set(None),
        "ctx_dept_id": ctx_dept_id.set(None),
        "ctx_data_scope": ctx_data_scope.set(None),
        "ctx_allowed_dept_ids": ctx_allowed_dept_ids.set(None),
        "ctx_is_superuser": ctx_is_superuser.set(None),
    }


def clear_data_permission_context(tokens: Optional[ContextTokens] = None) -> None:
    """
    清理数据权限上下文。
    - 传入 tokens 时使用 reset(token) 恢复到进入请求前的状态。
    - 未传入 tokens 时退化为显式置空（兼容旧调用方）。
    """
    if tokens:
        ctx_user_id.reset(tokens["ctx_user_id"])
        ctx_dept_id.reset(tokens["ctx_dept_id"])
        ctx_data_scope.reset(tokens["ctx_data_scope"])
        ctx_allowed_dept_ids.reset(tokens["ctx_allowed_dept_ids"])
        ctx_is_superuser.reset(tokens["ctx_is_superuser"])
        return
    ctx_user_id.set(None)
    ctx_dept_id.set(None)
    ctx_data_scope.set(None)
    ctx_allowed_dept_ids.set(None)
    ctx_is_superuser.set(None)
