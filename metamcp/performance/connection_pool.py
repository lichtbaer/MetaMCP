"""
Database Connection Pool

This module provides optimized database connection pooling for better performance.
"""

import asyncio
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import QueuePool

from ..config import get_settings
from ..utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class DatabaseConnectionPool:
    """Optimized database connection pool."""

    def __init__(self, database_url: str = None):
        """Initialize database connection pool."""
        self.database_url = database_url or settings.database_url
        self._engine: Optional[AsyncEngine] = None
        self._session_factory: Optional[async_sessionmaker] = None
        self._lock = asyncio.Lock()

    async def _create_engine(self) -> AsyncEngine:
        """Create async database engine with optimized settings."""
        if self._engine is None:
            # Configure connection pool
            pool_config = {
                "poolclass": QueuePool,
                "pool_size": settings.database_pool_size,
                "max_overflow": settings.database_max_overflow,
                "pool_timeout": settings.database_pool_timeout,
                "pool_recycle": settings.database_pool_recycle,
                "pool_pre_ping": True,  # Verify connections before use
                "echo": settings.debug,  # SQL logging in debug mode
            }

            # Create engine
            self._engine = create_async_engine(self.database_url, **pool_config)

            # Create session factory
            self._session_factory = async_sessionmaker(
                bind=self._engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False,
            )

            logger.info(f"Database connection pool initialized: {self.database_url}")
            logger.info(
                f"Pool size: {settings.database_pool_size}, "
                f"Max overflow: {settings.database_max_overflow}"
            )

        return self._engine

    async def get_engine(self) -> AsyncEngine:
        """Get database engine."""
        if self._engine is None:
            async with self._lock:
                await self._create_engine()
        return self._engine

    async def get_session_factory(self) -> async_sessionmaker:
        """Get session factory."""
        if self._session_factory is None:
            await self.get_engine()
        return self._session_factory

    @asynccontextmanager
    async def get_session(self):
        """Get database session with automatic cleanup."""
        session_factory = await self.get_session_factory()
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    async def get_pool_status(self) -> Dict[str, Any]:
        """Get connection pool status."""
        try:
            engine = await self.get_engine()
            pool = engine.pool

            return {
                "pool_size": pool.size(),
                "checked_in": pool.checkedin(),
                "checked_out": pool.checkedout(),
                "overflow": pool.overflow(),
                "invalid": pool.invalid(),
                "total_connections": pool.size() + pool.overflow(),
            }
        except Exception as e:
            logger.error(f"Failed to get pool status: {e}")
            return {}

    async def close(self):
        """Close database connections."""
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None
            logger.info("Database connection pool closed")


# Global database pool instance
_database_pool: Optional[DatabaseConnectionPool] = None


def get_database_pool(database_url: str = None) -> DatabaseConnectionPool:
    """Get global database pool instance."""
    global _database_pool
    if _database_pool is None:
        _database_pool = DatabaseConnectionPool(database_url)
    return _database_pool


async def close_database_pool():
    """Close global database pool."""
    global _database_pool
    if _database_pool is not None:
        await _database_pool.close()
        _database_pool = None
