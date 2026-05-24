from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .errors import ApiError, error_response
from .routes import assets, health, tasks, upload_preview
from .state import state


def create_app() -> FastAPI:
    app = FastAPI(title="Image-to-Figma Backend", version=state.settings.version)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=state.settings.cors_allow_origins,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )
    app.add_exception_handler(ApiError, lambda _request, error: error_response(error))
    app.include_router(health.router)
    app.include_router(upload_preview.router)
    app.include_router(tasks.router)
    app.include_router(assets.router)
    app.mount("/files/uploads", StaticFiles(directory=state.storage.uploads_dir), name="uploads")
    app.mount("/files/assets", StaticFiles(directory=state.storage.assets_dir), name="assets")
    return app


app = create_app()
