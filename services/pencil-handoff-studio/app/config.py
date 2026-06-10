from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    storage_root: Path
    max_upload_bytes: int
    max_files: int
    cors_allow_origins: list[str]
    yolo_model: Path | None
    yolo_conf: float
    yolo_iou: float
    yolo_imgsz: int
    yolo_device: str
    m29extract_path: Path | None
    psdlike_root: Path
    ocr_provider: str


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def service_root() -> Path:
    return Path(__file__).resolve().parents[1]


def get_settings() -> Settings:
    root = repo_root()
    return Settings(
        storage_root=Path(os.getenv("PENCIL_HANDOFF_STORAGE_ROOT", service_root() / "storage")).expanduser().resolve(),
        max_upload_bytes=int(os.getenv("PENCIL_HANDOFF_MAX_UPLOAD_BYTES", str(10 * 1024 * 1024))),
        max_files=max(0, int(os.getenv("PENCIL_HANDOFF_MAX_FILES", "0"))),
        cors_allow_origins=parse_csv(os.getenv("PENCIL_HANDOFF_CORS_ALLOW_ORIGINS", "*")),
        yolo_model=resolve_path(os.getenv("PENCIL_HANDOFF_YOLO_MODEL") or os.getenv("PENCIL_ASSET_YOLO_MODEL")),
        yolo_conf=float(os.getenv("PENCIL_HANDOFF_YOLO_CONF", os.getenv("PENCIL_ASSET_YOLO_CONF", "0.18"))),
        yolo_iou=float(os.getenv("PENCIL_HANDOFF_YOLO_IOU", os.getenv("PENCIL_ASSET_YOLO_IOU", "0.45"))),
        yolo_imgsz=max(1, int(os.getenv("PENCIL_HANDOFF_YOLO_IMGSZ", os.getenv("PENCIL_ASSET_YOLO_IMGSZ", "640")))),
        yolo_device=os.getenv("PENCIL_HANDOFF_YOLO_DEVICE", os.getenv("PENCIL_ASSET_YOLO_DEVICE", "auto")).strip() or "auto",
        m29extract_path=resolve_m29extract(root),
        psdlike_root=Path(
            os.getenv("PENCIL_HANDOFF_PSDLIKE_ROOT", os.getenv("PENCIL_ASSET_PSDLIKE_ROOT", root / "services" / "psdlike-python"))
        )
        .expanduser()
        .resolve(),
        ocr_provider=os.getenv("OCR_PROVIDER", "none").strip().lower() or "none",
    )


def resolve_path(value: str | None) -> Path | None:
    if not value or not value.strip():
        return None
    return Path(value).expanduser().resolve()


def resolve_m29extract(root: Path) -> Path | None:
    configured = resolve_path(os.getenv("PENCIL_HANDOFF_M29EXTRACT") or os.getenv("PENCIL_ASSET_M29EXTRACT"))
    if configured:
        return configured
    found = shutil.which("m29extract")
    if found:
        return Path(found).resolve()
    local = root / "services" / "backend-go" / "bin" / "m29extract"
    return local.resolve() if local.exists() else None


def parse_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]
