from __future__ import annotations

import shutil
from pathlib import Path


class Storage:
    def __init__(self, root: Path, public_base_url: str) -> None:
        self.root = root
        self.public_base_url = public_base_url.rstrip("/")
        self.uploads_dir = root / "uploads"
        self.assets_dir = root / "assets"
        self.dsl_dir = root / "dsl"
        self.primitives_dir = root / "primitives"
        self.logs_dir = root / "logs"
        self.ensure_dirs()

    def ensure_dirs(self) -> None:
        for directory in [self.uploads_dir, self.assets_dir, self.dsl_dir, self.primitives_dir, self.logs_dir]:
            directory.mkdir(parents=True, exist_ok=True)

    def upload_path(self, task_id: str) -> Path:
        return self.uploads_dir / task_id / "original.png"

    def banner_path(self, task_id: str) -> Path:
        return self.assets_dir / task_id / "banner.png"

    def region_path(self, task_id: str, region_name: str) -> Path:
        return self.assets_dir / task_id / f"{region_name}.png"

    def dsl_path(self, task_id: str) -> Path:
        return self.dsl_dir / f"{task_id}.json"

    def primitive_path(self, task_id: str) -> Path:
        return self.primitives_dir / f"{task_id}.json"

    def original_url(self, task_id: str) -> str:
        return f"{self.public_base_url}/files/uploads/{task_id}/original.png"

    def banner_url(self, task_id: str) -> str:
        return f"{self.public_base_url}/files/assets/{task_id}/banner.png"

    def region_url(self, task_id: str, region_name: str) -> str:
        return f"{self.public_base_url}/files/assets/{task_id}/{region_name}.png"

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

    def save_region_asset(self, task_id: str, region_name: str, data: bytes) -> Path:
        path = self.region_path(task_id, region_name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def save_primitives(self, task_id: str, data: str) -> Path:
        path = self.primitive_path(task_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data, encoding="utf-8")
        return path
