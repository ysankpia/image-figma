from __future__ import annotations

from typing import Any

try:
    import orjson
except ImportError:  # pragma: no cover - production dependency should be present.
    orjson = None  # type: ignore[assignment]


def dumps_pretty(data: Any) -> str:
    if orjson is None:
        import json

        return json.dumps(data, ensure_ascii=False, indent=2)
    return orjson.dumps(data, option=orjson.OPT_INDENT_2).decode("utf-8")


def dumps_compact(data: Any) -> str:
    if orjson is None:
        import json

        return json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return orjson.dumps(data).decode("utf-8")


def loads(text_or_bytes: str | bytes | bytearray | memoryview) -> Any:
    if orjson is None:
        import json

        if isinstance(text_or_bytes, memoryview):
            text_or_bytes = text_or_bytes.tobytes()
        if isinstance(text_or_bytes, (bytes, bytearray)):
            text_or_bytes = text_or_bytes.decode("utf-8")
        return json.loads(text_or_bytes)
    return orjson.loads(text_or_bytes)
