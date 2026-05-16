from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    version: str
    storage_root: Path
    database_path: Path
    public_base_url: str
    max_upload_bytes: int
    cors_allow_origins: list[str]
    visual_primitive_provider: str
    openai_api_key: str | None
    openai_vision_model: str
    openai_timeout_seconds: float


def get_settings() -> Settings:
    backend_root = Path(__file__).resolve().parents[1]
    storage_root = Path(os.getenv("STORAGE_ROOT", backend_root / "storage")).resolve()
    database_path = Path(os.getenv("DATABASE_PATH", storage_root / "app.db")).resolve()
    return Settings(
        version="0.1.0",
        storage_root=storage_root,
        database_path=database_path,
        public_base_url=os.getenv("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/"),
        max_upload_bytes=int(os.getenv("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024))),
        cors_allow_origins=parse_csv(os.getenv("CORS_ALLOW_ORIGINS", "*")),
        visual_primitive_provider=os.getenv("VISUAL_PRIMITIVE_PROVIDER", "fake").strip().lower() or "fake",
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_vision_model=os.getenv("OPENAI_VISION_MODEL", "gpt-5.5").strip() or "gpt-5.5",
        openai_timeout_seconds=float(os.getenv("OPENAI_TIMEOUT_SECONDS", "30")),
    )


def parse_csv(value: str) -> list[str]:
    items = [item.strip() for item in value.split(",")]
    return [item for item in items if item]
