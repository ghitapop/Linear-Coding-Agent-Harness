"""Database connection management for the Autonomous Orchestrator Framework."""

import os
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from database.models import Base


class DatabaseManager:
    """Manages database connections and sessions."""

    _instance: Optional["DatabaseManager"] = None

    def __init__(
        self,
        database_url: Optional[str] = None,
        echo: bool = False,
        pool_size: int = 5,
        max_overflow: int = 10,
    ) -> None:
        """Initialize the database manager.

        Args:
            database_url: PostgreSQL connection URL.
                         If not provided, uses DATABASE_URL env var.
            echo: If True, log all SQL statements.
            pool_size: Number of connections to maintain in the pool.
            max_overflow: Maximum overflow connections above pool_size.
        """
        self._database_url = database_url or os.environ.get("DATABASE_URL")
        if not self._database_url:
            raise ValueError(
                "Database URL is required. "
                "Provide via argument or DATABASE_URL environment variable."
            )

        # Convert postgres:// to postgresql+asyncpg://
        url = self._database_url
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)

        self._engine: AsyncEngine = create_async_engine(
            url,
            echo=echo,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_pre_ping=True,
        )
        self._session_factory = async_sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )

    @classmethod
    def get_instance(cls, **kwargs: object) -> "DatabaseManager":
        """Get the singleton database manager instance.

        Args:
            **kwargs: Arguments passed to DatabaseManager constructor
                     if creating a new instance.

        Returns:
            The singleton DatabaseManager instance.
        """
        if cls._instance is None:
            cls._instance = cls(**kwargs)  # type: ignore[arg-type]
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance. Useful for testing."""
        cls._instance = None

    @property
    def engine(self) -> AsyncEngine:
        """Get the SQLAlchemy async engine."""
        return self._engine

    async def create_tables(self) -> None:
        """Create all database tables.

        Uses SQLAlchemy's create_all which is idempotent.
        """
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def drop_tables(self) -> None:
        """Drop all database tables.

        WARNING: This will delete all data.
        """
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """Get a database session.

        Usage:
            async with db_manager.session() as session:
                # use session
                await session.commit()

        Yields:
            An async database session.
        """
        session = self._session_factory()
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    async def close(self) -> None:
        """Close the database connection pool."""
        await self._engine.dispose()


@asynccontextmanager
async def get_db_session(
    database_url: Optional[str] = None,
) -> AsyncIterator[AsyncSession]:
    """Get a database session using the singleton manager.

    This is a convenience function that gets or creates the
    DatabaseManager singleton and returns a session.

    Args:
        database_url: Optional database URL. Only used if the
                     singleton hasn't been initialized yet.

    Yields:
        An async database session.
    """
    manager = DatabaseManager.get_instance(database_url=database_url)
    async with manager.session() as session:
        yield session
