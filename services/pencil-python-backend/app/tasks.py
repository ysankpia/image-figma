from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from .config import Settings
from .project_builder import export_project
from .storage import TaskPaths, TaskStorage
from .types import ExportRequest, PageInput


class TaskManager:
    def __init__(self, storage: TaskStorage, settings: Settings) -> None:
        self.storage = storage
        self.settings = settings
        self.executor = ThreadPoolExecutor(max_workers=settings.max_workers, thread_name_prefix="pencil-export")

    def submit(
        self,
        *,
        paths: TaskPaths,
        inputs: list[PageInput],
        project_name: str,
        mode: str,
        columns: str,
        include_debug: bool,
        ocr_provider: str | None,
        boundary_source: str,
    ) -> None:
        self.executor.submit(
            self._run,
            paths=paths,
            inputs=inputs,
            project_name=project_name,
            mode=mode,
            columns=columns,
            include_debug=include_debug,
            ocr_provider=ocr_provider,
            boundary_source=boundary_source,
        )

    def _run(
        self,
        *,
        paths: TaskPaths,
        inputs: list[PageInput],
        project_name: str,
        mode: str,
        columns: str,
        include_debug: bool,
        ocr_provider: str | None,
        boundary_source: str,
    ) -> None:
        try:
            self.storage.patch_status(
                paths,
                status="running",
                pageCount=len(inputs),
                modes=selected_mode_list(mode),
                boundarySource=boundary_source,
            )
            manifest = export_project(
                ExportRequest(
                    inputs=inputs,
                    out_dir=paths.output,
                    project_name=project_name,
                    mode=mode,  # type: ignore[arg-type]
                    columns=columns,
                    include_debug=include_debug,
                    ocr_provider=ocr_provider,
                    boundary_source=boundary_source,  # type: ignore[arg-type]
                ),
                self.settings,
            )
            self.storage.patch_status(
                paths,
                status="completed",
                pageCount=manifest["pageCount"],
                modes=manifest["modes"],
                boundarySource=manifest.get("boundarySource", boundary_source),
                warnings=manifest.get("warnings", []),
                downloadUrl=f"/api/pencil/projects/{paths.task_id}/download.zip",
                manifestPath=str(paths.output / "manifest.json"),
                zipPath=str(paths.output / "project.zip"),
            )
        except Exception as error:
            self.storage.patch_status(paths, status="failed", error=str(error))


def selected_mode_list(mode: str) -> list[str]:
    if mode == "all":
        return ["clean-editable", "visual-fidelity", "visual-ocr"]
    return [mode]
