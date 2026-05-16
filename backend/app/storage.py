from __future__ import annotations

import shutil
import struct
from dataclasses import dataclass
from pathlib import Path


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


@dataclass(frozen=True)
class PngMetadata:
    width: int
    height: int


class Storage:
    def __init__(self, root: Path, public_base_url: str) -> None:
        self.root = root
        self.public_base_url = public_base_url.rstrip("/")
        self.uploads_dir = root / "uploads"
        self.assets_dir = root / "assets"
        self.dsl_dir = root / "dsl"
        self.logs_dir = root / "logs"
        self.ensure_dirs()

    def ensure_dirs(self) -> None:
        for directory in [self.uploads_dir, self.assets_dir, self.dsl_dir, self.logs_dir]:
            directory.mkdir(parents=True, exist_ok=True)

    def upload_path(self, task_id: str) -> Path:
        return self.uploads_dir / task_id / "original.png"

    def banner_path(self, task_id: str) -> Path:
        return self.assets_dir / task_id / "banner.png"

    def dsl_path(self, task_id: str) -> Path:
        return self.dsl_dir / f"{task_id}.json"

    def original_url(self, task_id: str) -> str:
        return f"{self.public_base_url}/files/uploads/{task_id}/original.png"

    def banner_url(self, task_id: str) -> str:
        return f"{self.public_base_url}/files/assets/{task_id}/banner.png"

    def save_upload(self, task_id: str, data: bytes) -> Path:
        path = self.upload_path(task_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def create_banner_asset(self, task_id: str, upload_path: Path) -> Path:
        path = self.banner_path(task_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(upload_path, path)
        return path


def is_png(data: bytes) -> bool:
    return data.startswith(PNG_SIGNATURE)


def read_png_metadata(data: bytes) -> PngMetadata | None:
    if not is_png(data) or len(data) < 33:
        return None

    ihdr_length = struct.unpack(">I", data[8:12])[0]
    chunk_type = data[12:16]
    if ihdr_length != 13 or chunk_type != b"IHDR":
        return None

    width, height = struct.unpack(">II", data[16:24])
    if width <= 0 or height <= 0:
        return None

    return PngMetadata(width=width, height=height)
