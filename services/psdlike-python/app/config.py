from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    root_dir: Path = Path(__file__).resolve().parents[1]
    storage_dir: Path = Path(__file__).resolve().parents[1] / "storage" / "tasks"


def get_settings() -> Settings:
    return Settings()
