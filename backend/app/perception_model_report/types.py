from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPORT_ONLY_META = {
    "reportOnly": True,
    "dslChanged": False,
    "assetChanged": False,
    "createdVisibleNodeCount": 0,
    "materializationChanged": False,
    "sourceOwnershipChanged": False,
    "cleanupAuthorized": False,
    "blockingUpload": False,
    "noSpecializedTextFilenameThemeOrFixedBboxRules": True,
}


@dataclass(frozen=True)
class PerceptionModelOptions:
    input_size: int = 960
    score_threshold: float = 0.05
    nms_threshold: float = 0.45
    top_k: int = 80
    min_box_px: float = 3.0
    provider: str = "CPUExecutionProvider"

    def to_dict(self) -> dict[str, Any]:
        return {
            "inputSize": self.input_size,
            "scoreThreshold": self.score_threshold,
            "nmsThreshold": self.nms_threshold,
            "topK": self.top_k,
            "minBoxPx": self.min_box_px,
            "provider": self.provider,
        }


@dataclass(frozen=True)
class PerceptionModelReportResult:
    report: dict[str, Any]
    output_dir: Path
