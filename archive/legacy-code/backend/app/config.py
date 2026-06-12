from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


_LOCAL_ENV_LOADED = False


@dataclass(frozen=True)
class Settings:
    version: str
    storage_root: Path
    database_path: Path
    public_base_url: str
    max_upload_bytes: int
    cors_allow_origins: list[str]
    ocr_provider: str
    ocr_min_confidence: float = 0.70
    baidu_paddle_ocr_token: str | None = None
    baidu_paddle_ocr_job_url: str = "https://paddleocr.aistudio-app.com/api/v2/ocr/jobs"
    baidu_paddle_ocr_model: str = "PP-OCRv5"
    baidu_paddle_ocr_poll_interval_seconds: float = 5
    baidu_paddle_ocr_timeout_seconds: float = 120
    upload_preview_profile: str = "production"


def get_settings() -> Settings:
    backend_root = Path(__file__).resolve().parents[1]
    load_local_env_file(backend_root.parent / ".env.local")
    storage_root = Path(os.getenv("STORAGE_ROOT", backend_root / "storage")).resolve()
    database_path = Path(os.getenv("DATABASE_PATH", storage_root / "app.db")).resolve()
    return Settings(
        version="0.1.0",
        storage_root=storage_root,
        database_path=database_path,
        public_base_url=os.getenv("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/"),
        max_upload_bytes=int(os.getenv("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024))),
        cors_allow_origins=parse_csv(os.getenv("CORS_ALLOW_ORIGINS", "*")),
        ocr_provider=os.getenv("OCR_PROVIDER", "fake").strip().lower() or "fake",
        ocr_min_confidence=float(os.getenv("OCR_MIN_CONFIDENCE", "0.70")),
        baidu_paddle_ocr_token=os.getenv("BAIDU_PADDLE_OCR_TOKEN"),
        baidu_paddle_ocr_job_url=os.getenv(
            "BAIDU_PADDLE_OCR_JOB_URL",
            "https://paddleocr.aistudio-app.com/api/v2/ocr/jobs",
        ).rstrip("/"),
        baidu_paddle_ocr_model=os.getenv("BAIDU_PADDLE_OCR_MODEL", "PP-OCRv5").strip() or "PP-OCRv5",
        baidu_paddle_ocr_poll_interval_seconds=float(os.getenv("BAIDU_PADDLE_OCR_POLL_INTERVAL_SECONDS", "5")),
        baidu_paddle_ocr_timeout_seconds=float(os.getenv("BAIDU_PADDLE_OCR_TIMEOUT_SECONDS", "120")),
        upload_preview_profile=parse_upload_preview_profile(os.getenv("UPLOAD_PREVIEW_PROFILE", "production")),
    )


def load_local_env_file(path: Path) -> None:
    global _LOCAL_ENV_LOADED
    if _LOCAL_ENV_LOADED:
        return
    _LOCAL_ENV_LOADED = True
    if os.getenv("IMAGE_FIGMA_LOAD_LOCAL_ENV", "true").strip().lower() in {"0", "false", "no", "off"}:
        return
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        parsed = parse_env_line(raw_line)
        if parsed is None:
            continue
        key, value = parsed
        os.environ.setdefault(key, value)


def parse_env_line(raw_line: str) -> tuple[str, str] | None:
    line = raw_line.strip()
    if not line or line.startswith("#"):
        return None
    if line.startswith("export "):
        line = line[len("export ") :].strip()
    if "=" not in line:
        return None
    key, value = line.split("=", 1)
    key = key.strip()
    if not key or key[0].isdigit() or not key.replace("_", "").isalnum():
        return None
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return key, value


def parse_csv(value: str) -> list[str]:
    items = [item.strip() for item in value.split(",")]
    return [item for item in items if item]


def parse_upload_preview_profile(value: str) -> str:
    profile = value.strip().lower() or "production"
    if profile not in {"production", "development"}:
        return "production"
    return profile


def parse_bool(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if not normalized:
        return default
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default
