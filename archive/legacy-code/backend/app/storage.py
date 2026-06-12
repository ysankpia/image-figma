from __future__ import annotations

from pathlib import Path


class Storage:
    def __init__(self, root: Path, public_base_url: str) -> None:
        self.root = root
        self.public_base_url = public_base_url.rstrip("/")
        self.uploads_dir = root / "uploads"
        self.assets_dir = root / "assets"
        self.dsl_dir = root / "dsl"
        self.ocr_dir = root / "ocr"
        self.logs_dir = root / "logs"
        self.ensure_dirs()

    def ensure_dirs(self) -> None:
        for directory in [
            self.uploads_dir,
            self.assets_dir,
            self.dsl_dir,
            self.ocr_dir,
            self.logs_dir,
        ]:
            directory.mkdir(parents=True, exist_ok=True)

    def upload_path(self, task_id: str) -> Path:
        return self.uploads_dir / task_id / "original.png"

    def save_upload(self, task_id: str, data: bytes) -> Path:
        path = self.upload_path(task_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path
