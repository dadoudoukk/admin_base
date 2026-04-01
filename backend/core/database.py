from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


# 默认使用 sqlite，便于快速启动；后续可改成 MySQL/PostgreSQL
# 例如：mysql+pymysql://user:password@127.0.0.1:3306/geeker_admin
DATABASE_URL = "mysql+pymysql://root:root@127.0.0.1:3306/geeker_admin?charset=utf8mb4"

is_sqlite = DATABASE_URL.startswith("sqlite")
engine = create_engine(
    DATABASE_URL,
    future=True,
    echo=False,
    pool_pre_ping=True,   # MySQL 推荐
    connect_args={"check_same_thread": False} if is_sqlite else {},
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    future=True,
)


class Base(DeclarativeBase):
    pass

