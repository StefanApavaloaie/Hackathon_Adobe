import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import Settings, get_settings
from app.errors import ServiceNotConfigured
from app.routers import campaigns, health, pages, runs, tracking, usage, webhooks

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="Win-back Agent API")

    @app.exception_handler(ServiceNotConfigured)
    async def service_not_configured(_: Request, exc: ServiceNotConfigured) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=503)

    # Handled here rather than in an exception handler so that error responses
    # pass back through CORS. Otherwise the browser reports a misleading CORS error.
    @app.middleware("http")
    async def catch_unhandled_errors(request: Request, call_next):
        try:
            return await call_next(request)
        except Exception:
            logger.exception("Unhandled error on %s %s", request.method, request.url.path)
            return JSONResponse({"detail": "Internal server error"}, status_code=500)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    for module in (health, runs, campaigns, usage, pages, tracking, webhooks):
        app.include_router(module.router)

    return app


app = create_app()
