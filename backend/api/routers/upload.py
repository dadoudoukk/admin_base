import shutil
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, File, Header, Request, UploadFile

from api.deps import make_response, require_user
from core.paths import UPLOAD_DIR

router = APIRouter(prefix="/file", tags=["文件上传"])


@router.post("/upload")
@router.post("/upload/img")
async def file_upload(
    request: Request,
    file: UploadFile = File(...),
    x_access_token: Optional[str] = Header(default=None, alias="x-access-token"),
) -> Dict[str, Any]:
    ctx = require_user(x_access_token)
    if not ctx:
        return make_response(401, data={}, msg="登录过期，请重新登录")

    orig = (file.filename or "file").strip()
    suffix = Path(orig).suffix
    if suffix:
        suffix = suffix.lower()
    else:
        suffix = ""
    new_name = f"{uuid.uuid4().hex}{suffix}"
    dest = UPLOAD_DIR / new_name
    try:
        with dest.open("wb") as out:
            shutil.copyfileobj(file.file, out)
    finally:
        await file.close()

    base = str(request.base_url).rstrip("/")
    file_url = f"{base}/uploads/{new_name}"
    return make_response(200, data={"fileUrl": file_url}, msg="上传成功")
