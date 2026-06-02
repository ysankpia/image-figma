from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import router

app = FastAPI(title="PSD-like Python Draft Service", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://www.figma.com", "http://localhost:8000"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
