from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any


EXAMPLE_DSL_PATH = Path(__file__).resolve().parents[2] / "packages" / "dsl-schema" / "examples" / "mobile-home.dsl.json"


def build_fake_dsl(*, task_id: str, original_url: str, banner_url: str) -> dict[str, Any]:
    with EXAMPLE_DSL_PATH.open("r", encoding="utf-8") as file:
        dsl = json.load(file)

    dsl = copy.deepcopy(dsl)
    dsl["taskId"] = task_id

    for asset in dsl.get("assets", []):
        if asset.get("assetId") == "asset_original":
            asset["url"] = original_url
            asset["storage"] = "local"
        if asset.get("assetId") == "asset_banner":
            asset["url"] = banner_url
            asset["storage"] = "local"

    dsl.setdefault("meta", {})
    dsl["meta"]["source"] = "backend_fake"
    return dsl
