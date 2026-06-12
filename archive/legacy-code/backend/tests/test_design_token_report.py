from __future__ import annotations

from pathlib import Path

from app.design_token_report import extract_m29_design_token_report


def test_design_token_report_empty_is_report_only(tmp_path: Path) -> None:
    report = token_report(tmp_path, dsl={"version": "0.1", "root": {"id": "root", "type": "frame", "layout": {}, "children": []}})

    assert report["summary"]["colorTokenCount"] == 0
    assert report["summary"]["textStyleTokenCount"] == 0
    assert report["summary"]["radiusTokenCount"] == 0
    assert report["summary"]["spacingTokenCount"] == 0
    assert report["summary"]["dslChanged"] is False
    assert report["summary"]["figmaVariablesBound"] is False
    assert report["summary"]["designSystemChanged"] is False
    assert report["summary"]["singlePageOnly"] is True


def test_color_tokens_are_collected_from_page_root_and_elements(tmp_path: Path) -> None:
    report = token_report(tmp_path, dsl=sample_dsl())

    values = {token["value"]: token for token in report["colorTokens"]}
    assert "#FFFFFF" in values
    assert "#111111" in values
    assert "#FF0000" in values
    assert values["#FF0000"]["count"] == 2


def test_text_style_tokens_group_matching_text_styles(tmp_path: Path) -> None:
    report = token_report(tmp_path, dsl=sample_dsl())

    token = next(item for item in report["textStyleTokens"] if item["fontSize"] == 14)
    assert token["fontFamily"] == "Inter"
    assert token["fontWeight"] == 400
    assert token["color"] == "#111111"
    assert token["count"] == 2


def test_radius_tokens_collect_numeric_and_corner_radius_values(tmp_path: Path) -> None:
    dsl = sample_dsl()
    dsl["root"]["children"].append(
        {
            "id": "card",
            "type": "shape",
            "layout": {"x": 0, "y": 70, "width": 20, "height": 20},
            "style": {"fill": "#00FF00", "radius": {"topLeft": 8, "topRight": 8, "bottomRight": 4, "bottomLeft": 4}},
        }
    )
    report = token_report(tmp_path, dsl=dsl)

    values = {token["value"]: token for token in report["radiusTokens"]}
    assert values[8]["count"] == 2
    assert values[4]["count"] == 2


def test_spacing_tokens_collect_positive_sibling_gaps(tmp_path: Path) -> None:
    report = token_report(tmp_path, dsl=sample_dsl())

    horizontal_values = {token["value"] for token in report["spacingTokens"] if token["axis"] == "horizontal"}
    assert 10 in horizontal_values


def test_non_hex_colors_are_skipped(tmp_path: Path) -> None:
    dsl = sample_dsl()
    dsl["root"]["children"].append(
        {
            "id": "gradient_like",
            "type": "shape",
            "layout": {"x": 0, "y": 120, "width": 20, "height": 20},
            "style": {"fill": "rgb(1, 2, 3)", "color": "#123"},
        }
    )
    report = token_report(tmp_path, dsl=dsl)

    colors = {token["value"] for token in report["colorTokens"]}
    assert "rgb(1, 2, 3)" not in colors
    assert "#123" not in colors


def token_report(tmp_path: Path, *, dsl: dict) -> dict:
    result = extract_m29_design_token_report(
        task_id="task_design_tokens",
        dsl=dsl,
        materialization_report={"schemaName": "M29PlanMaterializationReport", "schemaVersion": "0.1"},
        m295_report={"schemaName": "M295ReplayPlan", "schemaVersion": "0.1"},
        output_dir=tmp_path / "m29_design_tokens",
    )
    assert (tmp_path / "m29_design_tokens" / "design_token_report.json").exists()
    return result.report


def sample_dsl() -> dict:
    return {
        "version": "0.1",
        "page": {"background": {"type": "color", "value": "#ffffff"}},
        "root": {
            "id": "root",
            "type": "frame",
            "layout": {"x": 0, "y": 0, "width": 200, "height": 200},
            "style": {"fill": "#FFFFFF"},
            "children": [
                {
                    "id": "text_1",
                    "type": "text",
                    "layout": {"x": 0, "y": 0, "width": 40, "height": 16},
                    "style": {"color": "#111111", "fontFamily": "Inter", "fontSize": 14, "fontWeight": 400},
                },
                {
                    "id": "text_2",
                    "type": "text",
                    "layout": {"x": 50, "y": 0, "width": 40, "height": 16},
                    "style": {"color": "#111111", "fontFamily": "Inter", "fontSize": 14, "fontWeight": 400},
                },
                {
                    "id": "shape_1",
                    "type": "shape",
                    "layout": {"x": 100, "y": 0, "width": 40, "height": 16},
                    "style": {"fill": "#ff0000", "radius": 6},
                },
                {
                    "id": "shape_2",
                    "type": "shape",
                    "layout": {"x": 150, "y": 0, "width": 40, "height": 16},
                    "style": {"fill": "#FF0000", "radius": 6},
                },
            ],
        },
    }
