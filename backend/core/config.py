"""
应用配置：从环境变量与 backend/.env 加载（勿在代码中硬编码密钥与连接串）。
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parent.parent

# 唯一使用的 .env 路径（与当前工作目录无关）；修改连接串请改此文件。
SETTINGS_ENV_FILE = _BACKEND_DIR / ".env"


class Settings(BaseSettings):
    """与 Geeker-Admin 后端约定一致的环境变量名（大写下划线）。

    加载顺序（后者覆盖前者）：.env 文件 → 进程环境变量。
    若系统/IDE/conda 里设置了 DATABASE_URL，会覆盖 backend/.env 中的同名项。
    """

    model_config = SettingsConfigDict(
        env_file=SETTINGS_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(
        ...,
        description="SQLAlchemy 数据库 URL，如 mysql+aiomysql://user:pass@host:3306/db?charset=utf8mb4",
    )

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, v: object) -> object:
        """去掉 .env 行尾 \\r、首尾空格等，避免 URL 解析出的密码与手输不一致（表现为 1045）。"""
        if isinstance(v, str):
            # strip() 去掉行尾 \\n\\r 与首尾空格；BOM 偶发出现在 .env 首行
            s = v.strip().replace("\ufeff", "")
            # 部分编辑器会给 .env 值加整段引号，会导致 URL 整体非法或密码多字符
            if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
                s = s[1:-1].strip()
            return s
        return v

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
