from __future__ import annotations

import hashlib
import re
from pathlib import Path


def safe_slug(value: str, fallback: str = "item") -> str:
    slug = re.sub(r"[^0-9A-Za-z_-]+", "_", value).strip("_")
    return slug or fallback


def stable_page_id(path: Path, index: int) -> str:
    digest = hashlib.sha1(str(path.resolve()).encode("utf-8")).hexdigest()[:8]
    return f"page_{index:04d}_{safe_slug(path.stem, 'image')}_{digest}"


def mode_dir_name(mode: str) -> str:
    return "production" if mode == "clean-editable" else mode
