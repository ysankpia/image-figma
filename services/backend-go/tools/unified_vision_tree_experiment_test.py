#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path

import unified_vision_tree_experiment as tree


def sample_input() -> dict:
    evidence = [
        ev("e1", 0, 0, 20, 10),
        ev("e2", 24, 0, 20, 10),
        ev("e3", 0, 20, 44, 12),
        ev("e4", 0, 40, 44, 12),
    ]
    return {
        "version": "unified_vision_input.v1",
        "sourceImage": {"width": 100, "height": 100},
        "batches": [
            {
                "id": "batch_1",
                "sectionId": "section_1",
                "sectionBBox": {"x": 0, "y": 0, "width": 100, "height": 100},
                "cropBBox": {"x": 0, "y": 0, "width": 100, "height": 100},
                "evidence": evidence,
            }
        ],
    }


def ev(eid: str, x: int, y: int, width: int, height: int) -> dict:
    return {
        "id": eid,
        "roleHint": "text",
        "bbox": {"x": x, "y": y, "width": width, "height": height},
        "bboxLocal": {"x": x, "y": y, "width": width, "height": height},
        "text": eid,
    }


def result(nodes: list[dict], roots: list[str] | None = None) -> dict:
    return {
        "version": tree.RESULT_VERSION,
        "batches": [
            {
                "batchId": "batch_1",
                "sectionId": "section_1",
                "attempt": 1,
                "result": {
                    "version": tree.RESULT_VERSION,
                    "nodes": nodes,
                    "roots": roots if roots is not None else [nodes[-1]["id"]],
                    "ungrouped": [],
                    "warnings": [],
                },
            }
        ],
    }


class UnifiedVisionTreeExperimentTest(unittest.TestCase):
    def assert_reason(self, validation: dict, code: str) -> None:
        reasons = [item["reason"].split(":", 1)[0] for item in validation["rejectedNodes"]]
        self.assertIn(code, reasons, json.dumps(validation, indent=2))

    def test_parse_result_text_accepts_json_fence(self):
        parsed = tree.parse_result_text(
            """```json
{"version":"unified_vision_tree_result.v1","nodes":[],"roots":[],"ungrouped":[]}
```"""
        )
        self.assertEqual(parsed["version"], tree.RESULT_VERSION)

    def test_accepts_horizontal_row(self):
        validation = tree.validate_tree(
            sample_input(),
            result([
                {"id": "g1", "direction": "horizontal", "children": ["e1", "e2"], "gap": 4, "confidence": 0.9}
            ]),
        )
        self.assertEqual(validation["summary"]["errorCount"], 0, validation)
        self.assertEqual(validation["summary"]["acceptedLeafCount"], 2)

    def test_accepts_vertical_card_with_nested_row(self):
        validation = tree.validate_tree(
            sample_input(),
            result(
                [
                    {"id": "row_1", "direction": "horizontal", "children": ["e1", "e2"], "gap": 4, "confidence": 0.9},
                    {"id": "card_1", "direction": "vertical", "children": ["row_1", "e3", "e4"], "gap": 8, "confidence": 0.9},
                ],
                roots=["card_1"],
            ),
        )
        self.assertEqual(validation["summary"]["errorCount"], 0, validation)
        self.assertEqual(validation["summary"]["acceptedLeafCount"], 4)

    def test_rejects_unknown_evidence(self):
        validation = tree.validate_tree(
            sample_input(),
            result([
                {"id": "g1", "direction": "horizontal", "children": ["e1", "missing"], "gap": 4, "confidence": 0.9}
            ]),
        )
        self.assert_reason(validation, "unknown_child_ref")

    def test_rejects_duplicate_group_id(self):
        validation = tree.validate_tree(
            sample_input(),
            result([
                {"id": "g1", "direction": "horizontal", "children": ["e1", "e2"], "gap": 4, "confidence": 0.9},
                {"id": "g1", "direction": "vertical", "children": ["e3", "e4"], "gap": 4, "confidence": 0.9},
            ]),
        )
        self.assert_reason(validation, "duplicate_group_id")

    def test_rejects_cycle_and_self_reference(self):
        validation = tree.validate_tree(
            sample_input(),
            result(
                [
                    {"id": "g1", "direction": "horizontal", "children": ["g2", "e1"], "gap": 4, "confidence": 0.9},
                    {"id": "g2", "direction": "vertical", "children": ["g1", "e2"], "gap": 4, "confidence": 0.9},
                    {"id": "g3", "direction": "horizontal", "children": ["g3", "e3"], "gap": 4, "confidence": 0.9},
                ],
                roots=["g1", "g3"],
            ),
        )
        self.assert_reason(validation, "cycle")
        self.assert_reason(validation, "self_reference")

    def test_rejects_one_child_group(self):
        validation = tree.validate_tree(
            sample_input(),
            result([
                {"id": "g1", "direction": "horizontal", "children": ["e1"], "gap": 4, "confidence": 0.9}
            ]),
        )
        self.assert_reason(validation, "one_child_group")

    def test_rejects_duplicate_leaf_owner(self):
        validation = tree.validate_tree(
            sample_input(),
            result(
                [
                    {"id": "g1", "direction": "horizontal", "children": ["e1", "e2"], "gap": 4, "confidence": 0.9},
                    {"id": "g2", "direction": "horizontal", "children": ["e1", "e3"], "gap": 4, "confidence": 0.9},
                ],
                roots=["g1", "g2"],
            ),
        )
        self.assert_reason(validation, "duplicate_leaf_owner")

    def test_rejects_multi_parent_group(self):
        validation = tree.validate_tree(
            sample_input(),
            result(
                [
                    {"id": "row", "direction": "horizontal", "children": ["e1", "e2"], "gap": 4, "confidence": 0.9},
                    {"id": "parent_1", "direction": "vertical", "children": ["row", "e3"], "gap": 4, "confidence": 0.9},
                    {"id": "parent_2", "direction": "vertical", "children": ["row", "e4"], "gap": 4, "confidence": 0.9},
                ],
                roots=["parent_1", "parent_2"],
            ),
        )
        self.assert_reason(validation, "multi_parent_group")

    def test_ignores_low_confidence(self):
        validation = tree.validate_tree(
            sample_input(),
            result([
                {"id": "g1", "direction": "horizontal", "children": ["e1", "e2"], "gap": 4, "confidence": 0.4}
            ]),
        )
        self.assertEqual(validation["summary"]["errorCount"], 0, validation)
        self.assertEqual(validation["summary"]["ignoredNodeCount"], 1)
        self.assertEqual(validation["summary"]["acceptedLeafCount"], 0)

    def test_rejects_horizontal_overflow(self):
        input_doc = sample_input()
        input_doc["batches"][0]["evidence"] = [ev("e1", 0, 0, 40, 10), ev("e2", 42, 0, 40, 10)]
        validation = tree.validate_tree(
            input_doc,
            result([
                {"id": "g1", "direction": "horizontal", "children": ["e1", "e2"], "gap": 20, "confidence": 0.9}
            ]),
        )
        self.assert_reason(validation, "required_size_overflow")

    def test_rejects_cross_axis_spread_and_gap_variance(self):
        input_doc = sample_input()
        input_doc["batches"][0]["evidence"] = [
            ev("e1", 0, 0, 10, 10),
            ev("e2", 20, 40, 10, 10),
            ev("e3", 130, 0, 10, 10),
        ]
        validation = tree.validate_tree(
            input_doc,
            result([
                {"id": "g1", "direction": "horizontal", "children": ["e1", "e2", "e3"], "gap": 4, "confidence": 0.9}
            ]),
        )
        self.assert_reason(validation, "cross_axis_spread_high")
        self.assert_reason(validation, "actual_gap_too_large")

    def test_cli_fixture_writes_result_and_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "input.json"
            image_path = root / "source.png"
            fixture_path = root / "fixture.txt"
            result_path = root / "result.json"
            validation_path = root / "validation.json"
            input_path.write_text(json.dumps(sample_input()), encoding="utf-8")
            image_path.write_bytes(minimal_png())
            fixture_path.write_text(
                json.dumps(
                    {
                        "version": tree.RESULT_VERSION,
                        "nodes": [
                            {"id": "g1", "direction": "horizontal", "children": ["e1", "e2"], "gap": 4, "confidence": 0.9}
                        ],
                        "roots": ["g1"],
                        "ungrouped": [],
                        "warnings": [],
                    }
                ),
                encoding="utf-8",
            )
            code = tree.main(
                [
                    "--input",
                    str(input_path),
                    "--image",
                    str(image_path),
                    "--result-out",
                    str(result_path),
                    "--validation-out",
                    str(validation_path),
                    "--fixture-response",
                    str(fixture_path),
                ]
            )
            self.assertEqual(code, 0)
            self.assertTrue(result_path.exists())
            self.assertTrue(validation_path.exists())


def minimal_png() -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x02\x00\x00\x00\x02"
        b"\x08\x02\x00\x00\x00\xfd\xd4\x9as\x00\x00\x00\x0cIDATx\x9cc```\x00"
        b"\x00\x00\x04\x00\x01\xf6\x178U\x00\x00\x00\x00IEND\xaeB`\x82"
    )


if __name__ == "__main__":
    unittest.main()
