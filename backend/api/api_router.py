from fastapi import APIRouter

from api.routers import (
    auth,
    biz_fragment,
    biz_news,
    dict_data,
    dict_type,
    menu,
    role,
    sys_api,
    sys_log,
    upload,
    user,
)

router = APIRouter()
router.include_router(auth.router)
router.include_router(user.router)
router.include_router(role.router)
router.include_router(menu.router)
router.include_router(dict_type.router)
router.include_router(dict_data.router)
router.include_router(biz_news.router)
router.include_router(biz_fragment.router)
router.include_router(sys_log.router)
router.include_router(sys_api.router)
router.include_router(upload.router)
