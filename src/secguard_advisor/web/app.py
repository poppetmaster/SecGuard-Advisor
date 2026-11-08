"""Fábrica de la aplicación FastAPI."""

from collections.abc import Callable
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import text

from secguard_advisor.config import Settings, get_settings
from secguard_advisor.db.engine import create_engine_for_settings, create_session_factory
from secguard_advisor.db.recovery import reconcile_startup
from secguard_advisor.web.errors import AppError, error_response
from secguard_advisor.web.routes import cases

_WEB_DIR = Path(__file__).parent
_ALLOWED_HOSTS = {"127.0.0.1", "localhost", "testserver"}


def _default_ollama_probe(settings: Settings) -> bool:
    try:
        response = httpx.get(f"{settings.ollama_base_url}/api/tags", timeout=1.0)
    except httpx.HTTPError:
        return False
    return response.status_code == 200


def _origin_is_allowed(request: Request) -> bool:
    source = request.headers.get("origin") or request.headers.get("referer")
    if not source:
        return False
    host = urlsplit(source).hostname
    return host in _ALLOWED_HOSTS


def create_app(
    settings: Settings | None = None,
    ollama_probe: Callable[[], bool] | None = None,
) -> FastAPI:
    """Construye la aplicación con sus dependencias."""
    resolved = settings or get_settings()
    probe = ollama_probe or (lambda: _default_ollama_probe(resolved))

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        resolved.ensure_directories()
        engine = create_engine_for_settings(resolved)
        factory = create_session_factory(engine)
        app.state.settings = resolved
        app.state.engine = engine
        app.state.session_factory = factory
        with factory() as session:
            reconcile_startup(session)
        yield
        engine.dispose()

    app = FastAPI(
        title="SecGuard Advisor",
        version=resolved.app_version,
        lifespan=lifespan,
    )
    app.state.ollama_probe = probe
    app.state.templates = Jinja2Templates(directory=str(_WEB_DIR / "templates"))
    app.mount("/static", StaticFiles(directory=str(_WEB_DIR / "static")), name="static")
    app.include_router(cases.router)

    @app.get("/")
    def root():
        return RedirectResponse(url="/cases", status_code=303)

    @app.middleware("http")
    async def origin_guard(request: Request, call_next):
        if request.method in {"POST", "PUT", "PATCH", "DELETE"} and not _origin_is_allowed(request):
            return error_response("forbidden_origin")
        return await call_next(request)

    @app.get("/healthz")
    def healthz(request: Request):
        database_ok = True
        try:
            with request.app.state.session_factory() as session:
                session.execute(text("SELECT 1"))
        except Exception:
            database_ok = False

        ollama_ok = bool(request.app.state.ollama_probe())
        payload = {
            "status": "ok" if database_ok else "degraded",
            "database": "ok" if database_ok else "error",
            "ollama": "ok" if ollama_ok else "unavailable",
        }
        return JSONResponse(
            status_code=200 if database_ok else 503,
            content=payload,
        )

    @app.exception_handler(AppError)
    async def app_error_handler(_request: Request, exc: AppError):
        return error_response(exc.code, exc.message)

    @app.exception_handler(404)
    async def not_found_handler(_request: Request, _exc):
        return error_response("not_found")

    @app.exception_handler(Exception)
    async def internal_error_handler(_request: Request, _exc):
        return error_response("internal_error")

    return app
