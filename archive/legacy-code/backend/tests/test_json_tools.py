from __future__ import annotations

from app.json_tools import dumps_compact, dumps_pretty, loads


def test_dumps_pretty_preserves_chinese_text() -> None:
    data = {"text": "充值", "items": [{"label": "提币"}]}

    output = dumps_pretty(data)

    assert isinstance(output, str)
    assert "充值" in output
    assert "\\u5145" not in output
    assert "\n  " in output
    assert loads(output) == data


def test_dumps_compact_uses_compact_json_without_ascii_escape() -> None:
    data = {"text": "买币", "value": 3}

    output = dumps_compact(data)

    assert output == '{"text":"买币","value":3}'
    assert loads(output.encode("utf-8")) == data


def test_loads_accepts_memoryview() -> None:
    payload = memoryview('{"ok":true,"label":"划转"}'.encode("utf-8"))

    assert loads(payload) == {"ok": True, "label": "划转"}
