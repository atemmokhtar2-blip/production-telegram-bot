from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()

_engine_kwargs: dict = {
    "echo": False,
    "future": True,
}

if settings.is_sqlite:
    # aiosqlite: NullPool is default-ish; enable WAL for concurrent reads
    _engine_kwargs["connect_args"] = {"check_same_thread": False, "timeout": 30}
    _engine_kwargs["poolclass"] = NullPool
else:
    # PostgreSQL / other: connection pool tuned for bot workloads
    _engine_kwargs["pool_size"] = 5
    _engine_kwargs["max_overflow"] = 10
    _engine_kwargs["pool_pre_ping"] = True
    _engine_kwargs["pool_recycle"] = 1800

engine = create_async_engine(settings.database_url, **_engine_kwargs)

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def init_db() -> None:
    from pathlib import Path

    if settings.is_sqlite:
        Path("data").mkdir(exist_ok=True)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if settings.is_sqlite:
            # WAL improves concurrent read performance under load
            await conn.exec_driver_sql("PRAGMA journal_mode=WAL")
            await conn.exec_driver_sql("PRAGMA synchronous=NORMAL")
            await conn.exec_driver_sql("PRAGMA temp_store=MEMORY")
            await conn.exec_driver_sql("PRAGMA busy_timeout=30000")


async def get_session():
    async with async_session_factory() as session:
        yield session
