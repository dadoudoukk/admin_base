import logging
from typing import Optional

from fastapi import Request
from sqlalchemy import select
from starlette.responses import Response

from api.deps import decode_access_token
from core.database import AsyncSessionLocal
from models import SysOperLog, SysUser

logger = logging.getLogger(__name__)


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64]
    if request.client:
        return (request.client.host or "")[:64]
    return ""


async def save_oper_log_async(
    access_token: Optional[str],
    request_method: str,
    request_url: str,
    request_ip: str,
    execute_time: int,
    status: int,
    error_msg: Optional[str],
    request_param: Optional[str],
) -> None:
    """后台任务内创建独立 AsyncSession，禁止复用请求会话。"""
    if AsyncSessionLocal is None:
        return
    async with AsyncSessionLocal() as db:
        try:
            user_name: Optional[str] = None
            if access_token:
                claims = decode_access_token(access_token)
                if claims and claims.get("user_id") is not None:
                    u = (
                        await db.scalars(
                            select(SysUser).where(SysUser.id == int(claims["user_id"]), SysUser.is_delete == 0)
                        )
                    ).first()
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
            await db.commit()
        except Exception:
            logger.exception("写入操作日志失败")
            await db.rollback()


def resolve_oper_log_status(response: Optional[Response], err: Optional[Exception]) -> tuple[int, Optional[str]]:
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


async def flush_oper_log_background(
    access_token: Optional[str],
    request_method: str,
    request_url: str,
    request_ip: str,
    execute_time_ms: int,
    status: int,
    error_msg: Optional[str],
    request_param: Optional[str],
) -> None:
    try:
        await save_oper_log_async(
            access_token,
            request_method,
            request_url,
            request_ip,
            execute_time_ms,
            status,
            error_msg,
            request_param,
        )
    except Exception:
        logger.exception("异步写入操作日志失败")
