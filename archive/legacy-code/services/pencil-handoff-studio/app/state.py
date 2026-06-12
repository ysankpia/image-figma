from __future__ import annotations

from dataclasses import dataclass

from .config import Settings, get_settings


@dataclass
class AppState:
    settings: Settings


state = AppState(settings=get_settings())
