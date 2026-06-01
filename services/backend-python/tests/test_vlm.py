from app.vlm import normalize_kind, normalize_role, parse_json_response


def test_parse_json_response_accepts_plain_json():
    payload, error = parse_json_response(
        '{"classifications":[{"candidateId":"cand_0001","role":"icon","kind":"image","decision":"emit","confidence":0.8,"reason":"ok"}],"warnings":[]}'
    )

    assert error == ""
    assert payload["classifications"][0]["candidateId"] == "cand_0001"


def test_parse_json_response_accepts_fenced_json():
    payload, error = parse_json_response(
        "```json\n{\"classifications\":[],\"warnings\":[]}\n```"
    )

    assert error == ""
    assert payload["classifications"] == []


def test_parse_json_response_rejects_malformed_json():
    payload, error = parse_json_response("not json")

    assert payload == {}
    assert error.startswith("json_parse_error")


def test_normalize_unknown_role_and_kind():
    assert normalize_role("not-a-role") == "unknown"
    assert normalize_kind("bad") == "suppress"
