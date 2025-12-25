"""FastAPI application for the Autonomous Orchestrator Framework."""

from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from server.api_routes import health_router, projects_router
from server.database.connection import DatabaseManager


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan handler.

    Handles startup and shutdown events.
    """
    # Startup
    db_manager = DatabaseManager.get_instance()
    await db_manager.create_tables()

    yield

    # Shutdown
    await db_manager.close()
    DatabaseManager.reset_instance()


def create_app(
    title: str = "Autonomous Orchestrator API",
    version: str = "1.0.0",
    database_url: Optional[str] = None,
    cors_origins: Optional[list[str]] = None,
) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        title: API title.
        version: API version.
        database_url: Optional database URL. Uses DATABASE_URL env var if not provided.
        cors_origins: Optional list of allowed CORS origins.

    Returns:
        Configured FastAPI application.
    """
    # Initialize database manager
    if database_url:
        DatabaseManager.get_instance(database_url=database_url)

    app = FastAPI(
        title=title,
        version=version,
        description="REST API for the Autonomous Orchestrator Framework",
        lifespan=lifespan,
    )

    # Configure CORS
    origins = cors_origins or ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers
    app.include_router(health_router)
    app.include_router(projects_router)

    @app.get("/")
    async def root() -> dict[str, str]:
        """Root endpoint."""
        return {
            "name": title,
            "version": version,
            "docs": "/docs",
        }

    return app


# Create default app instance for uvicorn
app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
    )
