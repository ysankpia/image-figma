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
    "materializerConsumesAssets": False,
    "blockingUpload": False,
    "noSpecializedTextFilenameThemeOrFixedBboxRules": True,
}


@dataclass(frozen=True)
class M29TransparentAssetResult:
    report: dict[str, Any]
    output_dir: Path
