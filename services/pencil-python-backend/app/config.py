from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from .types import BOUNDARY_SOURCES, BoundarySource


_LOCAL_ENV_LOADED = False


@dataclass(frozen=True)
class Settings:
    addr: str
    storage_root: Path
    m29extract_path: Path | None
    psdlike_root: Path
    psdlike_tile_size: int
    default_boundary_source: BoundarySource
    max_upload_bytes: int
    max_files: int
    max_workers: int
    cors_allow_origins: list[str]
    ocr_provider: str


def get_settings() -> Settings:
    service_root = Path(__file__).resolve().parents[1]
    repo_root = service_root.parents[1]
    load_local_env_file(repo_root / ".env.local")
    storage_root = Path(os.getenv("PENCIL_BACKEND_STORAGE_ROOT", service_root / "storage")).expanduser().resolve()
    return Settings(
        addr=os.getenv("PENCIL_BACKEND_ADDR", "127.0.0.1:8100"),
        storage_root=storage_root,
        m29extract_path=resolve_m29extract_path(os.getenv("PENCIL_BACKEND_M29EXTRACT")),
        psdlike_root=resolve_psdlike_root(os.getenv("PENCIL_BACKEND_PSDLIKE_ROOT")),
        psdlike_tile_size=max(1, int(os.getenv("PENCIL_BACKEND_PSDLIKE_TILE_SIZE", "8"))),
        default_boundary_source=parse_boundary_source(
            os.getenv("PENCIL_BACKEND_DEFAULT_BOUNDARY_SOURCE", "psdlike"),
            name="PENCIL_BACKEND_DEFAULT_BOUNDARY_SOURCE",
        ),
        max_upload_bytes=int(os.getenv("PENCIL_BACKEND_MAX_UPLOAD_BYTES", str(10 * 1024 * 1024))),
        max_files=int(os.getenv("PENCIL_BACKEND_MAX_FILES", "20")),
        max_workers=max(1, int(os.getenv("PENCIL_BACKEND_MAX_WORKERS", "1"))),
        cors_allow_origins=parse_csv(os.getenv("PENCIL_BACKEND_CORS_ALLOW_ORIGINS", "*")),
        ocr_provider=os.getenv("OCR_PROVIDER", "none").strip().lower() or "none",
    )


def resolve_m29extract_path(configured: str | None) -> Path | None:
    if configured and configured.strip():
        return Path(configured).expanduser().resolve()
    found = shutil.which("m29extract")
    if found:
        return Path(found).resolve()
    repo_root = Path(__file__).resolve().parents[3]
    local = repo_root / "services" / "backend-go" / "bin" / "m29extract"
    if local.exists():
        return local.resolve()
    return None


def parse_boundary_source(value: str, *, name: str = "boundarySource") -> BoundarySource:
    normalized = value.strip().lower()
    if normalized not in BOUNDARY_SOURCES:
        allowed = ", ".join(BOUNDARY_SOURCES)
        raise ValueError(f"unsupported {name}: {value}; expected one of {allowed}")
    return cast(BoundarySource, normalized)


def resolve_psdlike_root(configured: str | None) -> Path:
    if configured and configured.strip():
        return Path(configured).expanduser().resolve()
    repo_root = Path(__file__).resolve().parents[3]
    return (repo_root / "services" / "psdlike-python").resolve()


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
