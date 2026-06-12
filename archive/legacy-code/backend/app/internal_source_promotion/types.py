from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPORT_META = {
    "dslChanged": False,
    "assetChanged": False,
    "createdVisibleNodeCount": 0,
    "materializationChanged": False,
    "promotionOnly": True,
    "noSpecializedTextFilenameThemeOrFixedBboxRules": True,
}


@dataclass(frozen=True)
class M29InternalSourcePromotionResult:
    report: dict[str, Any]
    m292_document: dict[str, Any]
    output_dir: Path
