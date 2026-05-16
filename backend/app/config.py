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
    ocr_provider: str
    dsl_patch_mode: str
    openai_api_key: str | None
    openai_vision_model: str
    openai_timeout_seconds: float
    ocr_min_confidence: float = 0.70
    baidu_paddle_ocr_token: str | None = None
    baidu_paddle_ocr_job_url: str = "https://paddleocr.aistudio-app.com/api/v2/ocr/jobs"
    baidu_paddle_ocr_model: str = "PP-OCRv5"
    baidu_paddle_ocr_poll_interval_seconds: float = 5
    baidu_paddle_ocr_timeout_seconds: float = 120
    text_replacement_mode: str = "debug"
    text_replacement_max_blocks: int = 20
    text_replacement_min_confidence: float = 0.95
    text_replacement_solid_bg_tolerance: int = 18
    text_replacement_max_height: int = 64
    text_replacement_min_width: int = 12
    text_replacement_min_height: int = 10


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
        ocr_provider=os.getenv("OCR_PROVIDER", "fake").strip().lower() or "fake",
        ocr_min_confidence=float(os.getenv("OCR_MIN_CONFIDENCE", "0.70")),
        dsl_patch_mode=os.getenv("DSL_PATCH_MODE", "debug").strip().lower() or "debug",
        baidu_paddle_ocr_token=os.getenv("BAIDU_PADDLE_OCR_TOKEN"),
        baidu_paddle_ocr_job_url=os.getenv(
            "BAIDU_PADDLE_OCR_JOB_URL",
            "https://paddleocr.aistudio-app.com/api/v2/ocr/jobs",
        ).rstrip("/"),
        baidu_paddle_ocr_model=os.getenv("BAIDU_PADDLE_OCR_MODEL", "PP-OCRv5").strip() or "PP-OCRv5",
        baidu_paddle_ocr_poll_interval_seconds=float(os.getenv("BAIDU_PADDLE_OCR_POLL_INTERVAL_SECONDS", "5")),
        baidu_paddle_ocr_timeout_seconds=float(os.getenv("BAIDU_PADDLE_OCR_TIMEOUT_SECONDS", "120")),
        text_replacement_mode=os.getenv("TEXT_REPLACEMENT_MODE", "debug").strip().lower() or "debug",
        text_replacement_max_blocks=int(os.getenv("TEXT_REPLACEMENT_MAX_BLOCKS", "20")),
        text_replacement_min_confidence=float(os.getenv("TEXT_REPLACEMENT_MIN_CONFIDENCE", "0.95")),
        text_replacement_solid_bg_tolerance=int(os.getenv("TEXT_REPLACEMENT_SOLID_BG_TOLERANCE", "18")),
        text_replacement_max_height=int(os.getenv("TEXT_REPLACEMENT_MAX_HEIGHT", "64")),
        text_replacement_min_width=int(os.getenv("TEXT_REPLACEMENT_MIN_WIDTH", "12")),
        text_replacement_min_height=int(os.getenv("TEXT_REPLACEMENT_MIN_HEIGHT", "10")),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_vision_model=os.getenv("OPENAI_VISION_MODEL", "gpt-5.5").strip() or "gpt-5.5",
        openai_timeout_seconds=float(os.getenv("OPENAI_TIMEOUT_SECONDS", "30")),
    )


def parse_csv(value: str) -> list[str]:
    items = [item.strip() for item in value.split(",")]
    return [item for item in items if item]
