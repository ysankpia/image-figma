from __future__ import annotations

from importlib import import_module
from types import ModuleType


MODULE_NAMES = [
    "schema",
    "colors",
    "ocr",
    "masks",
    "components",
    "evidence",
    "candidates",
    "surfaces",
    "controls",
    "media_text",
    "ownership",
    "assets",
    "style",
    "layers",
    "dsl",
    "previews",
    "reports",
]


def wire_runtime_namespace() -> None:
    """Restore the old V1 single-file global namespace for mechanically split modules."""
    modules = [_load_module(name) for name in MODULE_NAMES]
    symbols: dict[str, object] = {}
    for module in modules:
        for name, value in module.__dict__.items():
            if name.startswith("_"):
                continue
            symbols[name] = value
    for module in modules:
        module.__dict__.update(symbols)


def _load_module(name: str) -> ModuleType:
    return import_module(f"{__package__}.{name}")
