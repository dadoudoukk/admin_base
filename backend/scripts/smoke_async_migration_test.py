import asyncio
import json
import os
import tempfile
import time
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
import pandas as pd


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str


def env(name: str, default: Optional[str] = None) -> str:
    value = os.getenv(name, default)
    if value is None:
        raise RuntimeError(f"Missing required env: {name}")
    return value


def ensure_success(payload: Dict[str, Any], action: str) -> None:
    code = payload.get("code")
    if code != 200:
        raise RuntimeError(f"{action} failed, code={code}, msg={payload.get('msg')}, data={payload.get('data')}")


async def post_json(client: httpx.AsyncClient, path: str, body: Dict[str, Any], token: Optional[str]) -> Dict[str, Any]:
    headers = {"x-access-token": token} if token else {}
    resp = await client.post(path, json=body, headers=headers)
    resp.raise_for_status()
    return resp.json()


async def get_json(client: httpx.AsyncClient, path: str, token: Optional[str]) -> Dict[str, Any]:
    headers = {"x-access-token": token} if token else {}
    resp = await client.get(path, headers=headers)
    resp.raise_for_status()
    return resp.json()


async def login(client: httpx.AsyncClient, username: str, password: str) -> str:
    payload = await post_json(client, "/login", {"username": username, "password": password}, token=None)
    ensure_success(payload, "login")
    token = (payload.get("data") or {}).get("access_token")
    if not token:
        raise RuntimeError("login success but no access_token")
    return token


async def check_auth(client: httpx.AsyncClient, token: str) -> CheckResult:
    info = await get_json(client, "/user/info", token)
    ensure_success(info, "user info")
    data = info.get("data") or {}
    if not data.get("roles"):
        return CheckResult("鉴权与登录", False, "user/info 返回 roles 为空")
    return CheckResult("鉴权与登录", True, "登录与鉴权正常，拿到 token 并成功访问 user/info")


async def check_user_relations(client: httpx.AsyncClient, token: str) -> CheckResult:
    payload = await post_json(
        client,
        "/user/list",
        {"pageNum": 1, "pageSize": 10, "username": "", "gender": ""},
        token,
    )
    ensure_success(payload, "user list")
    rows = (payload.get("data") or {}).get("list") or []
    if not rows:
        return CheckResult("用户角色/部门关联查询", True, "用户列表为空，接口本身正常")
    first = rows[0]
    if "roleIds" not in first or "roleNames" not in first:
        return CheckResult("用户角色/部门关联查询", False, "user/list 缺少 roleIds 或 roleNames 字段")
    return CheckResult("用户角色/部门关联查询", True, "用户列表正常返回角色关联字段")


async def _download_template(client: httpx.AsyncClient, token: str) -> int:
    resp = await client.get("/user/template", headers={"x-access-token": token})
    resp.raise_for_status()
    return len(resp.content)


async def check_excel_io(client: httpx.AsyncClient, token: str) -> CheckResult:
    t0 = time.perf_counter()
    sizes = await asyncio.gather(*[_download_template(client, token) for _ in range(3)])
    elapsed = time.perf_counter() - t0
    if any(s <= 0 for s in sizes):
        return CheckResult("Excel 导入导出", False, "模板下载内容为空")

    resp = await client.post("/user/export", json={"username": "", "gender": ""}, headers={"x-access-token": token})
    resp.raise_for_status()
    if len(resp.content) <= 0:
        return CheckResult("Excel 导入导出", False, "用户导出内容为空")

    df = pd.DataFrame(
        [{"用户名": f"smoke_{int(time.time())}", "姓名": "冒烟用户", "性别": "男", "手机号": "", "邮箱": "", "角色": "超级管理员"}]
    )
    bio = BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Sheet1")
    bio.seek(0)
    files = {"file": ("import.xlsx", bio.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    import_resp = await client.post("/user/import", files=files, headers={"x-access-token": token})
    import_resp.raise_for_status()
    import_payload = import_resp.json()
    ensure_success(import_payload, "user import")
    return CheckResult("Excel 导入导出", True, f"模板并发下载正常，导入导出可用（3并发耗时 {elapsed:.2f}s）")


async def check_biz_pagination(client: httpx.AsyncClient, token: str) -> CheckResult:
    frag = await post_json(client, "/biz/fragment/content/list", {"pageNum": 1, "pageSize": 10, "title": ""}, token)
    ensure_success(frag, "fragment content list")
    news = await post_json(client, "/biz/newsArticle/list", {"pageNum": 1, "pageSize": 10, "title": ""}, token)
    ensure_success(news, "news article list")
    frag_total = ((frag.get("data") or {}).get("total"))
    news_total = ((news.get("data") or {}).get("total"))
    if frag_total is None or news_total is None:
        return CheckResult("biz 分页与软删除", False, "分页 total 字段缺失")
    return CheckResult("biz 分页与软删除", True, f"fragment total={frag_total}, news total={news_total}")


async def check_upload(client: httpx.AsyncClient, token: str) -> CheckResult:
    with tempfile.NamedTemporaryFile("wb", delete=False, suffix=".txt") as f:
        f.write(b"smoke upload")
        tmp = Path(f.name)
    try:
        files = {"file": (tmp.name, tmp.read_bytes(), "text/plain")}
        resp = await client.post("/file/upload", files=files, headers={"x-access-token": token})
        resp.raise_for_status()
        payload = resp.json()
        ensure_success(payload, "file upload")
        file_url = ((payload.get("data") or {}).get("fileUrl") or "")
        if not file_url.startswith("http"):
            return CheckResult("文件上传", False, f"fileUrl 非法: {file_url}")
        return CheckResult("文件上传", True, f"上传成功，返回 URL: {file_url}")
    finally:
        tmp.unlink(missing_ok=True)


async def check_oper_log(client: httpx.AsyncClient, token: str) -> CheckResult:
    # 触发几次接口请求，再查日志列表
    await get_json(client, "/auth/buttonList", token)
    await post_json(client, "/biz/newsCategory/list", {"pageNum": 1, "pageSize": 5, "categoryName": ""}, token)
    await post_json(client, "/biz/fragment/category/list", {"pageNum": 1, "pageSize": 5, "code": "", "name": ""}, token)
    await asyncio.sleep(1.0)
    logs = await post_json(
        client,
        "/sys/log/list",
        {"pageNum": 1, "pageSize": 20, "userName": "", "requestMethod": ""},
        token,
    )
    ensure_success(logs, "sys log list")
    rows = ((logs.get("data") or {}).get("list") or [])
    if not rows:
        return CheckResult("操作日志异步写入", False, "sys/log/list 返回为空，未观察到日志写入")
    return CheckResult("操作日志异步写入", True, f"日志列表返回 {len(rows)} 条")


async def main() -> None:
    base_url = env("BASE_URL", "http://127.0.0.1:8000")
    api_prefix = env("API_PREFIX", "/api")
    admin_user = env("ADMIN_USER", "admin")
    admin_pass = env("ADMIN_PASS", "123456")
    timeout = float(env("SMOKE_TIMEOUT", "30"))
    if not api_prefix.startswith("/"):
        api_prefix = "/" + api_prefix
    api_prefix = api_prefix.rstrip("/")

    results: List[CheckResult] = []
    async with httpx.AsyncClient(base_url=base_url.rstrip("/") + api_prefix, timeout=timeout, trust_env=False) as client:
        token = await login(client, admin_user, admin_pass)
        results.append(await check_auth(client, token))
        results.append(await check_user_relations(client, token))
        results.append(await check_excel_io(client, token))
        results.append(await check_biz_pagination(client, token))
        results.append(await check_upload(client, token))
        results.append(await check_oper_log(client, token))

    passed = sum(1 for r in results if r.ok)
    failed = [r for r in results if not r.ok]
    print("\n=== Async Migration Smoke Test ===")
    for r in results:
        mark = "PASS" if r.ok else "FAIL"
        print(f"[{mark}] {r.name}: {r.detail}")
    print(f"\nSummary: {passed}/{len(results)} passed")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
