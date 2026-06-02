from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    root_dir: Path = Path(__file__).resolve().parents[1]
    storage_dir: Path = Path(__file__).resolve().parents[1] / "storage" / "tasks"
    ocr_cache_dir: Path = Path(__file__).resolve().parents[1] / "storage" / "ocr_cache"
    ocr_provider: str = "baidu_ppocrv5"
    ocr_min_confidence: float = 0.70
    baidu_paddle_ocr_token: str = ""
    baidu_paddle_ocr_job_url: str = "https://paddleocr.aistudio-app.com/api/v2/ocr/jobs"
    baidu_paddle_ocr_model: str = "PP-OCRv5"
    baidu_paddle_ocr_poll_interval_seconds: float = 5.0
    baidu_paddle_ocr_timeout_seconds: float = 120.0
    psdlike_allow_missing_ocr: bool = False


def get_settings() -> Settings:
    load_dotenv_local()
    root_dir = Path(__file__).resolve().parents[1]
    return Settings(
        root_dir=root_dir,
        storage_dir=Path(os.getenv("PSDLIKE_STORAGE_DIR", str(root_dir / "storage" / "tasks"))).expanduser(),
        ocr_cache_dir=Path(os.getenv("PSDLIKE_OCR_CACHE_DIR", str(root_dir / "storage" / "ocr_cache"))).expanduser(),
        ocr_provider=os.getenv("OCR_PROVIDER", "baidu_ppocrv5").strip().lower() or "baidu_ppocrv5",
        ocr_min_confidence=float(os.getenv("OCR_MIN_CONFIDENCE", "0.70")),
        baidu_paddle_ocr_token=os.getenv("BAIDU_PADDLE_OCR_TOKEN", ""),
        baidu_paddle_ocr_job_url=os.getenv(
            "BAIDU_PADDLE_OCR_JOB_URL",
            "https://paddleocr.aistudio-app.com/api/v2/ocr/jobs",
        ),
        baidu_paddle_ocr_model=os.getenv("BAIDU_PADDLE_OCR_MODEL", "PP-OCRv5").strip() or "PP-OCRv5",
        baidu_paddle_ocr_poll_interval_seconds=float(os.getenv("BAIDU_PADDLE_OCR_POLL_INTERVAL_SECONDS", "5")),
        baidu_paddle_ocr_timeout_seconds=float(os.getenv("BAIDU_PADDLE_OCR_TIMEOUT_SECONDS", "120")),
        psdlike_allow_missing_ocr=_env_bool("PSDLIKE_ALLOW_MISSING_OCR", default=False),
    )


def load_dotenv_local() -> None:
    """Load the first .env.local found from cwd upward without overriding the shell."""
    cwd = Path.cwd()
    for directory in [cwd, *cwd.parents]:
        env_file = directory / ".env.local"
        if not env_file.is_file():
            continue
        for raw_line in env_file.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            line = line.removeprefix("export ").strip()
            key, separator, value = line.partition("=")
            if not separator:
                continue
            key = key.strip()
            value = value.strip().strip("\"'")
            if key and key not in os.environ:
                os.environ[key] = value
        return


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}
