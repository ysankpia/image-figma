from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import asset_projects, health
from .state import state


def create_app() -> FastAPI:
    app = FastAPI(title="Pencil Asset Backend", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=state.settings.cors_allow_origins,
        allow_methods=["GET", "POST", "PUT", "OPTIONS"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(asset_projects.router)
    return app


app = create_app()
