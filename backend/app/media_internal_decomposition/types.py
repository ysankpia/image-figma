from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


COMPOSITE_MEDIA_PIXEL_OWNER = "preserve_raster"
COMPOSITE_MEDIA_REPLAY_DECISION = "image_replay"
INTERNAL_CANDIDATE_TYPES = {"symbol", "shape", "unknown"}
REPORT_ONLY_META = {
    "reportOnly": True,
    "dslChanged": False,
    "assetChanged": False,
    "createdVisibleNodeCount": 0,
    "materializationChanged": False,
    "blockingUpload": False,
    "noSpecializedTextFilenameThemeOrFixedBboxRules": True,
}


@dataclass(frozen=True)
class M29MediaInternalDecompositionResult:
    report: dict[str, Any]
    output_dir: Path
