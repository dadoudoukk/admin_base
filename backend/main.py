import asyncio
import logging
import time
import traceback
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response

from api.api_router import router as core_router
from api.deps import make_response
from api.oper_log import client_ip, flush_oper_log_background, resolve_oper_log_status
from core.config import get_settings
from core.context import begin_data_permission_context_scope, clear_data_permission_context
from core.limiter import limiter
from core.paths import UPLOAD_DIR
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

logger = logging.getLogger(__name__)
_settings = get_settings()

app = FastAPI(title="Geeker-Admin FastAPI Auth Center")
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)


@app.middleware("http")
async def clear_data_permission_context_middleware(request: Request, call_next):
    tokens = begin_data_permission_context_scope()
    try:
        return await call_next(request)
    finally:
        clear_data_permission_context(tokens)


def _validation_error_message(exc: RequestValidationError) -> str:
    parts: List[str] = []
    for err in exc.errors()[:12]:
        loc = err.get("loc") or ()
        loc_s = ".".join(str(x) for x in loc if x != "body")
        msg = err.get("msg", "")
        if loc_s:
            parts.append(f"{loc_s}: {msg}")
        else:
            parts.append(str(msg))
    return "; ".join(parts) if parts else "请求参数不合法"


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    detail = _validation_error_message(exc)
    return JSONResponse(
        status_code=200,
        content={"code": 400, "msg": f"参数校验失败: {detail}", "data": None},
        headers={"X-Geeker-Code": "400"},
    )


@app.exception_handler(RateLimitExceeded)
async def rate_limit_exception_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content=make_response(429, data=None, msg="请求过于频繁，请稍后再试"),
        headers={"X-Geeker-Code": "429"},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    msg = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    return JSONResponse(
        status_code=200,
        content={"code": exc.status_code, "msg": msg, "data": None},
        headers={"X-Geeker-Code": str(exc.status_code)},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    traceback.print_exc()
    logger.error("未捕获异常: %s", exc, exc_info=(type(exc), exc, exc.__traceback__))
    return JSONResponse(
        status_code=200,
        content={"code": 500, "data": {}, "msg": str(exc)},
        headers={"X-Geeker-Code": "500"},
    )


@app.middleware("http")
async def oper_log_middleware(request: Request, call_next):
    method = request.method.upper()
    if method in ("GET", "HEAD", "OPTIONS"):
        return await call_next(request)

    path = request.url.path
    if path.startswith("/docs") or path in ("/openapi.json", "/redoc") or path.startswith("/redoc"):
        return await call_next(request)

    access_token = request.headers.get("x-access-token")
    ip = client_ip(request)
    url = path[:512]

    request_param_str: Optional[str] = None
    ct = (request.headers.get("content-type") or "").lower()
    if "multipart/form-data" in ct:
        request_param_str = "[multipart/form-data，未记录正文]"
    else:
        body_bytes = await request.body()
        if body_bytes:
            try:
                request_param_str = body_bytes.decode("utf-8")[:2000]
            except UnicodeDecodeError:
                request_param_str = body_bytes.decode("utf-8", errors="replace")[:2000]

        async def receive():
            return {"type": "http.request", "body": body_bytes}

        request._receive = receive  # type: ignore[method-assign]

    start = time.perf_counter()
    caught: Optional[Exception] = None
    response: Optional[Response] = None
    try:
        response = await call_next(request)
        return response
    except Exception as e:
        caught = e
        raise
    finally:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        status_val, err_msg = resolve_oper_log_status(response, caught)
        asyncio.create_task(
            flush_oper_log_background(
                access_token,
                method,
                url,
                ip,
                elapsed_ms,
                status_val,
                err_msg,
                request_param_str,
            )
        )


app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=_settings.cors_allow_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(core_router, prefix="/geeker")
app.include_router(core_router, prefix="/api")
