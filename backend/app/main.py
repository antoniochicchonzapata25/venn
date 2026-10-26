"""Venn FastAPI app: JSON API under /api, and the prebuilt React app for everything else."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.branding import APP_NAME, APP_VERSION
from app.config import FRONTEND_DIST, get_settings
from app.db import make_engine, make_session_factory
from app.migrations import upgrade_to_head
from app.routers import auth, body, coach, health, nutrition, profile, training
from app.security import LoginThrottle
from app.services.catalog import ensure_catalog

NOT_BUILT_PAGE = f"""<!doctype html><title>{APP_NAME}</title>
<body style="font-family:system-ui;background:#eef2f6;color:#253445;padding:3rem">
<h1>{APP_NAME} API is running</h1>
<p>The web interface has not been built. Run <code>npm ci &amp;&amp; npm run build</code> in <code>frontend/</code>,
or use the committed build from a fresh clone. API docs: <a href="/docs">/docs</a>.</p></body>"""


def create_app(database_url: str | None = None, run_migrations: bool = True, frontend_dist: Path = FRONTEND_DIST) -> FastAPI:
    url = database_url or get_settings().database_url

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if run_migrations:
            upgrade_to_head(url)
        with app.state.session_factory() as db:
            ensure_catalog(db)
        yield
        app.state.engine.dispose()

    app = FastAPI(title=f"{APP_NAME} API", version=APP_VERSION, lifespan=lifespan)
    app.state.engine = make_engine(url)
    app.state.session_factory = make_session_factory(app.state.engine)
    app.state.login_throttle = LoginThrottle()

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(profile.router)
    app.include_router(nutrition.router)
    app.include_router(training.router)
    app.include_router(coach.router)
    app.include_router(body.router)

    index = frontend_dist / "index.html"
    if (frontend_dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404, "Not found")
        candidate = (frontend_dist / path).resolve()
        if path and candidate.is_file() and frontend_dist.resolve() in candidate.parents:
            return FileResponse(candidate)
        if index.is_file():
            return FileResponse(index)
        return HTMLResponse(NOT_BUILT_PAGE)

    return app


app = create_app()
