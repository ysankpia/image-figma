from __future__ import annotations

from fastapi import FastAPI

from .api import router

app = FastAPI(title="Slice Studio PSD-like Text Style", version="0.1.0")
app.include_router(router)
