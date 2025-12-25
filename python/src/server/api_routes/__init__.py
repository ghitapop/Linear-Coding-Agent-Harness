"""API routes module."""

from server.api_routes.health import router as health_router
from server.api_routes.projects import router as projects_router

__all__ = ["health_router", "projects_router"]
