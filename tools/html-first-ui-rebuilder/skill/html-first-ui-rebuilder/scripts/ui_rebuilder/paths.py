from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RunPaths:
    root: Path

    @property
    def source_dir(self) -> Path:
        return self.root / "source"

    @property
    def work_dir(self) -> Path:
        return self.root / "work"

    @property
    def rois_dir(self) -> Path:
        return self.work_dir / "rois"

    @property
    def sheets_dir(self) -> Path:
        return self.work_dir / "sheets"

    @property
    def qwen_dir(self) -> Path:
        return self.work_dir / "qwen"

    @property
    def qwen_full_dir(self) -> Path:
        return self.work_dir / "qwen_full"

    @property
    def assets_dir(self) -> Path:
        return self.root / "assets"

    @property
    def run_json(self) -> Path:
        return self.root / "run.json"

    @property
    def asset_plan_json(self) -> Path:
        return self.root / "asset_plan.json"

    @property
    def sheet_manifest_json(self) -> Path:
        return self.root / "sheet_manifest.json"

    @property
    def qwen_manifest_json(self) -> Path:
        return self.root / "qwen_manifest.json"

    @property
    def qwen_full_manifest_json(self) -> Path:
        return self.root / "qwen_full_manifest.json"

    @property
    def asset_manifest_json(self) -> Path:
        return self.root / "asset_manifest.json"

    @property
    def preview_html(self) -> Path:
        return self.root / "preview.html"

    @property
    def report_md(self) -> Path:
        return self.root / "report.md"

    @property
    def diff_png(self) -> Path:
        return self.root / "diff.png"

    def ensure(self) -> None:
        for path in [
            self.root,
            self.source_dir,
            self.work_dir,
            self.rois_dir,
            self.sheets_dir,
            self.qwen_dir,
            self.qwen_full_dir,
            self.assets_dir,
        ]:
            path.mkdir(parents=True, exist_ok=True)
