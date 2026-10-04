from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from settings.db import DatabaseSettings


class DBClient:
    """Owns the engine + connection pool and hands out sessions.

    Knows nothing about seats or bookings. Callers that open a transaction own
    its boundary; code receiving the session must never commit or roll back.
    """

    def __init__(self, settings: DatabaseSettings) -> None:
        self._engine: AsyncEngine = create_async_engine(
            settings.url,
            pool_size=settings.pool_size,
            max_overflow=settings.max_overflow,
            pool_timeout=settings.pool_timeout_seconds,
            pool_pre_ping=True,
            echo=settings.echo,
        )
        # Same pool; connections checked out through this run in AUTOCOMMIT.
        autocommit_engine = self._engine.execution_options(isolation_level="AUTOCOMMIT")
        self._txn_sessions = async_sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )
        self._autocommit_sessions = async_sessionmaker(
            autocommit_engine, class_=AsyncSession, expire_on_commit=False
        )

    @property
    def engine(self) -> AsyncEngine:
        return self._engine

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[AsyncSession]:
        """BEGIN on enter; COMMIT on clean exit; ROLLBACK if anything raises."""
        async with self._txn_sessions() as session, session.begin():
            yield session

    @asynccontextmanager
    async def connection(self) -> AsyncIterator[AsyncSession]:
        """Autocommit session: every statement commits on its own.

        Use for single-statement reads/writes that need no atomicity across
        statements. Use `transaction()` for anything that does.
        """
        async with self._autocommit_sessions() as session:
            yield session

    async def dispose(self) -> None:
        """Close all pooled connections. Call on app shutdown."""
        await self._engine.dispose()
