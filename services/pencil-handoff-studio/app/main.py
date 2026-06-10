from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .routes import handoff_projects, health
from .state import state


def create_app() -> FastAPI:
    app = FastAPI(title="Pencil Handoff Studio", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=state.settings.cors_allow_origins,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(handoff_projects.router)

    web_dist = Path(__file__).resolve().parents[1] / "web" / "dist"
    if web_dist.exists():
        app.mount("/studio", StaticFiles(directory=web_dist, html=True), name="studio")
    return app


app = create_app()
