from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


UploadPreviewProfile = Literal["production", "development"]
UploadPreviewRuntimeMode = Literal["interactive", "full", "diagnostic"]


class UploadPreviewPipelineError(RuntimeError):
    def __init__(self, stage: str, code: str, message: str) -> None:
        super().__init__(message)
        self.stage = stage
        self.code = code


@dataclass(frozen=True)
class UploadPreviewArtifactPolicy:
    profile: UploadPreviewProfile
    emit_debug_artifacts: bool
    emit_preview_artifacts: bool
