import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import Settings, get_settings
from app.errors import ServiceNotConfigured
from app.routers import campaigns, health, pages, runs, sending, tracking, usage, webhooks

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

    # Every router is registered here, so neither feature branch needs to edit this file.
    for module in (health, runs, campaigns, usage, sending, pages, tracking, webhooks):
        app.include_router(module.router)

    @app.get("/")
    async def root():
        return {"message": "Win-back Agent API", "docs": "/docs"}

    return app


app = create_app()
