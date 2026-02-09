import contextlib
import os

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

# 使用绝对路径确保数据库文件位置正确
# 默认存储在 backend/data 目录下，名为 social_storage.db
BASE_DIR = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
# 使用新的数据库文件名以避免锁定问题
DATABASE_FILE = os.path.join(BASE_DIR, "data", "social_storage_v2.db")
DATABASE_URL = f"sqlite+aiosqlite:///{DATABASE_FILE}"

social_engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},  # 允许 SQLite 多线程
    pool_size=20,  # 增加连接池大小
    max_overflow=10,
    pool_timeout=30,  # 获取连接超时
)


async def init_social_db():
    """初始化社交数据库表"""
    # [Fix] Import models to ensure they are registered with SQLModel.metadata
    from . import models_db  # noqa: F401

    async with social_engine.begin() as conn:
        # 启用 WAL 模式以获得更好的并发性能
        await conn.execute(text("PRAGMA journal_mode=WAL;"))
        await conn.run_sync(SQLModel.metadata.create_all)

        # [迁移] 如果缺少 agent_id 列则添加（安全迁移）
        with contextlib.suppress(Exception):
            await conn.execute(
                text("ALTER TABLE qqmessage ADD COLUMN agent_id VARCHAR DEFAULT 'pero'")
            )

        with contextlib.suppress(Exception):
            await conn.execute(
                text(
                    "ALTER TABLE socialmemory ADD COLUMN agent_id VARCHAR DEFAULT 'pero'"
                )
            )


async def get_social_db_session():
    """获取社交数据库会话"""
    async_session = sessionmaker(
        social_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session
