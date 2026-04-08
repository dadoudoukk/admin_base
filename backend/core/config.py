"""
应用配置：从环境变量与 backend/.env 加载（勿在代码中硬编码密钥与连接串）。
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """与 Geeker-Admin 后端约定一致的环境变量名（大写下划线）。"""

    model_config = SettingsConfigDict(
        env_file=_BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(
        ...,
        description="SQLAlchemy 数据库 URL，如 mysql+aiomysql://user:pass@host:3306/db?charset=utf8mb4",
    )
    secret_key: str = Field(..., description="JWT 签名密钥")
    jwt_algorithm: str = Field(default="HS256", description="JWT 算法")
    access_token_expire_seconds: int = Field(default=86400, description="Access Token 有效期（秒）")
    cors_allow_origin_regex: str = Field(
        default=r"http://localhost(:\d+)?|http://127\.0\.0\.1(:\d+)?",
        description="CORS allow_origin_regex",
    )
    default_avatar_url: str = Field(
        default="https://api.dicebear.com/7.x/avataaars/svg?seed=admin",
        description="默认头像 URL",
    )
    redis_url: str = Field(
        default="redis://127.0.0.1:6379/0",
        description="Redis 连接 URL，如 redis://127.0.0.1:6379/0",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
