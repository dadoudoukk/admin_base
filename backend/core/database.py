from urllib.parse import unquote

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from core.config import get_settings

_settings = get_settings()
DATABASE_URL = _settings.database_url


def _sync_database_url(async_url: str) -> str:
    """将异步驱动 URL 转为同步 URL，供 init_db / DDL 使用（避免 async_engine.sync_engine 触发 MissingGreenlet）。"""
    u = make_url(async_url)
    dn = u.drivername
    if dn == "mysql+aiomysql":
        return str(u.set(drivername="mysql+pymysql"))
    if dn == "mariadb+aiomysql":
        return str(u.set(drivername="mariadb+pymysql"))
    if dn == "sqlite+aiosqlite":
        return str(u.set(drivername="sqlite"))
    if dn == "postgresql+asyncpg":
        return str(u.set(drivername="postgresql+psycopg2"))
    return async_url


async_engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    future=True,
)

_sync_url_str = _sync_database_url(DATABASE_URL)
_sync_parsed = make_url(_sync_url_str)
# 凭据一律从「原始异步 URL」解析，避免 driver 改写后再 str()/make_url 与手输密码不一致
_mysql_auth_u = make_url(DATABASE_URL)

if _sync_parsed.drivername.startswith("mysql"):
    # 与手写 pymysql.connect 参数一致；unquote 防止 % 编码密码与 .env 肉眼不一致
    def _pymysql_sync_creator():
        import pymysql

        u = _mysql_auth_u
        user = unquote(u.username) if u.username else None
        raw_pw = u.password
        password = unquote(raw_pw) if raw_pw is not None else ""
        return pymysql.connect(
            host=u.host or "localhost",
            port=int(u.port or 3306),
            user=user,
            password=password,
            database=u.database or None,
            charset="utf8mb4",
        )

    sync_engine = create_engine(
        "mysql+pymysql://",
        creator=_pymysql_sync_creator,
        echo=False,
        pool_pre_ping=True,
        future=True,
    )
else:
    sync_engine = create_engine(
        _sync_url_str,
        echo=False,
        pool_pre_ping=True,
        future=True,
    )

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    autoflush=False,
    expire_on_commit=False,
    class_=AsyncSession,
)


class Base(DeclarativeBase):
    pass

