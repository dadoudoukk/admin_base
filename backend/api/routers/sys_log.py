from datetime import datetime
from io import BytesIO
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import pandas as pd
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

from api.deps import get_async_db, make_response, require_user
from api.helpers import build_sys_log_export_query, oper_log_row
from models import SysOperLog
from schemas.system import SysOperLogExportBody, SysOperLogListBody

router = APIRouter(prefix="/sys/log", tags=["操作日志"])


@router.post("/list")
async def sys_oper_log_list(
    body: SysOperLogListBody,
    db: AsyncSession = Depends(get_async_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = await require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    q = select(SysOperLog).where(SysOperLog.is_delete == 0)
    if body.userName and body.userName.strip():
        q = q.where(SysOperLog.user_name.like(f"%{body.userName.strip()}%"))
    if body.requestMethod and body.requestMethod.strip():
        q = q.where(SysOperLog.request_method == body.requestMethod.strip().upper())

    total = len((await db.scalars(q)).all())
    rows = (
        await db.scalars(
            q.order_by(SysOperLog.create_time.desc())
            .offset((body.pageNum - 1) * body.pageSize)
            .limit(body.pageSize)
        )
    ).all()
    return make_response(
        200,
        data={
            "list": [oper_log_row(r) for r in rows],
            "pageNum": body.pageNum,
            "pageSize": body.pageSize,
            "total": total,
        },
        msg="success",
    )


@router.post("/export")
@router.get("/export")
async def sys_oper_log_export(
    body: Optional[SysOperLogExportBody] = None,
    userName: Optional[str] = None,
    requestMethod: Optional[str] = None,
    startTime: Optional[str] = None,
    endTime: Optional[str] = None,
    db: AsyncSession = Depends(get_async_db),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Response:
    ctx = await require_user(x_access_token)
    if not ctx:
        raise HTTPException(status_code=401, detail="登录过期，请重新登录")

    query_user_name = (body.userName if body else None) or userName
    query_request_method = (body.requestMethod if body else None) or requestMethod
    query_start_time = (body.startTime if body else None) or startTime
    query_end_time = (body.endTime if body else None) or endTime

    rows = await build_sys_log_export_query(
        db,
        query_user_name,
        query_request_method,
        query_start_time,
        query_end_time,
    )

    export_rows: List[Dict[str, Any]] = []
    for item in rows:
        export_rows.append(
            {
                "操作人": item.user_name or "",
                "请求方式": item.request_method,
                "操作模块": item.request_url,
                "请求路径": item.request_url,
                "操作IP": item.request_ip,
                "执行耗时(ms)": item.execute_time,
                "执行状态": "成功" if int(item.status) == 1 else "失败",
                "错误信息": item.error_msg or "",
                "请求参数": item.request_param or "",
                "操作时间": item.create_time.strftime("%Y-%m-%d %H:%M:%S") if item.create_time else "",
            }
        )

    df = pd.DataFrame(
        export_rows,
        columns=["操作人", "请求方式", "操作模块", "请求路径", "操作IP", "执行耗时(ms)", "执行状态", "错误信息", "请求参数", "操作时间"],
    )
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="系统日志")
    excel_bytes = output.getvalue()

    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    filename = f"系统日志_{ts}.xlsx"
    quoted_name = quote(filename)
    headers = {
        "Content-Disposition": f"attachment; filename={quoted_name}; filename*=UTF-8''{quoted_name}",
        "Content-Length": str(len(excel_bytes)),
    }
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )
