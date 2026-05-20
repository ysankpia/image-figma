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
    m30_preview_profile: str = "production"
    m31_upload_diagnostics_enabled: bool = True
    m31_upload_diagnostics_strict: bool = False
    ocr_text_editability_enabled: bool = True
    ocr_graphic_text_preserve_enabled: bool = True
    ocr_max_rotation_angle: float = 3.0
    ocr_max_background_texture: float = 0.45
    ocr_max_background_color_count: int = 32
    ocr_text_symbol_leakage_cleanup_enabled: bool = True
    m29_small_overlay_text_audit_enabled: bool = True
    m29_small_overlay_text_audit_strict: bool = False
    m29_small_overlay_text_reprobe_enabled: bool = False
    m29_small_overlay_text_max_candidates: int = 12
    m29_small_overlay_text_upscale_factor: int = 3
    m30_shape_erasure_enabled: bool = True
    m30_image_erasure_enabled: bool = True


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
        m30_preview_profile=parse_m30_preview_profile(os.getenv("M30_PREVIEW_PROFILE", "production")),
        m31_upload_diagnostics_enabled=parse_bool(os.getenv("M31_UPLOAD_DIAGNOSTICS_ENABLED", "true"), default=True),
        m31_upload_diagnostics_strict=parse_bool(os.getenv("M31_UPLOAD_DIAGNOSTICS_STRICT", "false"), default=False),
        ocr_text_editability_enabled=parse_bool(os.getenv("OCR_TEXT_EDITABILITY_ENABLED", "true"), default=True),
        ocr_graphic_text_preserve_enabled=parse_bool(
            os.getenv("OCR_GRAPHIC_TEXT_PRESERVE_ENABLED", os.getenv("OCR_ARTISTIC_TEXT_FILTER_ENABLED", "true")),
            default=True,
        ),
        ocr_max_rotation_angle=float(os.getenv("OCR_MAX_ROTATION_ANGLE", "3.0")),
        ocr_max_background_texture=float(os.getenv("OCR_MAX_BACKGROUND_TEXTURE", "0.45")),
        ocr_max_background_color_count=int(os.getenv("OCR_MAX_BACKGROUND_COLOR_COUNT", "32")),
        ocr_text_symbol_leakage_cleanup_enabled=parse_bool(os.getenv("OCR_TEXT_SYMBOL_LEAKAGE_CLEANUP_ENABLED", "true"), default=True),
        m29_small_overlay_text_audit_enabled=parse_bool(os.getenv("M29_SMALL_OVERLAY_TEXT_AUDIT_ENABLED", "true"), default=True),
        m29_small_overlay_text_audit_strict=parse_bool(os.getenv("M29_SMALL_OVERLAY_TEXT_AUDIT_STRICT", "false"), default=False),
        m29_small_overlay_text_reprobe_enabled=parse_bool(os.getenv("M29_SMALL_OVERLAY_TEXT_REPROBE_ENABLED", "false"), default=False),
        m29_small_overlay_text_max_candidates=int(os.getenv("M29_SMALL_OVERLAY_TEXT_MAX_CANDIDATES", "12")),
        m29_small_overlay_text_upscale_factor=int(os.getenv("M29_SMALL_OVERLAY_TEXT_UPSCALE_FACTOR", "3")),
        m30_shape_erasure_enabled=parse_bool(os.getenv("M30_SHAPE_ERASURE_ENABLED", "true"), default=True),
        m30_image_erasure_enabled=parse_bool(os.getenv("M30_IMAGE_ERASURE_ENABLED", "true"), default=True),
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


def parse_m30_preview_profile(value: str) -> str:
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
