#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import layout_advisor_experiment as advisor


class LayoutAdvisorExperimentTest(unittest.TestCase):
    def test_parse_result_text_accepts_json_fence(self):
        result = advisor.parse_result_text(
            """```json
{"version":"layout_advisor_result.v1","groups":[],"fallbackEvidenceIds":[],"warnings":[]}
```"""
        )
        self.assertEqual(result["version"], "layout_advisor_result.v1")
        self.assertEqual(result["groups"], [])

    def test_validate_result_shape_rejects_missing_groups(self):
        with self.assertRaises(RuntimeError):
            advisor.validate_result_shape({"version": "layout_advisor_result.v1"})

    def test_provider_headers_override_urllib_user_agent(self):
        headers = advisor.provider_headers("test-key")
        self.assertEqual(headers["Authorization"], "Bearer test-key")
        self.assertEqual(headers["Accept"], "application/json")
        self.assertIn("User-Agent", headers)
        self.assertNotIn("Python-urllib", headers["User-Agent"])

    def test_request_url_accepts_base_with_or_without_v1(self):
        self.assertEqual(
            advisor.request_url("https://example.test/openai", "/responses"),
            "https://example.test/openai/v1/responses",
        )
        self.assertEqual(
            advisor.request_url("https://example.test/openai/v1", "/responses"),
            "https://example.test/openai/v1/responses",
        )

    def test_compact_advisor_input_only_sends_flow_evidence(self):
        compact = advisor.compact_advisor_input(
            {
                "version": "layout_advisor_input.v1",
                "sourceImage": {"width": 100, "height": 100},
                "evidence": [
                    {
                        "id": "text_1",
                        "roleHint": "text",
                        "bbox": {"x": 1, "y": 2, "width": 3, "height": 4},
                        "text": "Keep",
                        "sourceRefs": [{"kind": "debug", "id": "large"}],
                    },
                    {
                        "id": "shape_1",
                        "roleHint": "shape",
                        "bbox": {"x": 5, "y": 6, "width": 7, "height": 8},
                    },
                ],
                "badRows": [{"id": "row_1", "flowEvidence": ["text_1"], "sourceRefs": [{"kind": "debug"}]}],
                "instructions": {"outputShape": "{}"},
            }
        )
        self.assertEqual([item["id"] for item in compact["flowEvidence"]], ["text_1"])
        self.assertNotIn("sourceRefs", compact["flowEvidence"][0])
        self.assertNotIn("sourceRefs", compact["badRows"][0])

    def test_cli_fixture_writes_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "layout_advisor_input.v1.json"
            image_path = root / "source.png"
            fixture_path = root / "fixture.txt"
            out_path = root / "layout_advisor_result.v1.json"
            input_path.write_text(json.dumps({"version": "layout_advisor_input.v1"}), encoding="utf-8")
            image_path.write_bytes(b"\x89PNG\r\n\x1a\n")
            fixture_path.write_text(
                json.dumps({"version": "layout_advisor_result.v1", "groups": [], "fallbackEvidenceIds": [], "warnings": []}),
                encoding="utf-8",
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).with_name("layout_advisor_experiment.py")),
                    "--input",
                    str(input_path),
                    "--image",
                    str(image_path),
                    "--out",
                    str(out_path),
                    "--fixture-response",
                    str(fixture_path),
                ],
                check=False,
                env={**os.environ},
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertTrue(out_path.exists())

    def test_cli_failure_writes_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "layout_advisor_input.v1.json"
            image_path = root / "source.png"
            fixture_path = root / "bad.txt"
            out_path = root / "layout_advisor_result.v1.json"
            fallback_path = root / "layout_advisor_fallback.v1.json"
            input_path.write_text(json.dumps({"version": "layout_advisor_input.v1"}), encoding="utf-8")
            image_path.write_bytes(b"\x89PNG\r\n\x1a\n")
            fixture_path.write_text("not json", encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).with_name("layout_advisor_experiment.py")),
                    "--input",
                    str(input_path),
                    "--image",
                    str(image_path),
                    "--out",
                    str(out_path),
                    "--fallback-out",
                    str(fallback_path),
                    "--fixture-response",
                    str(fixture_path),
                ],
                check=False,
                env={**os.environ},
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(completed.returncode, 0)
            fallback = json.loads(fallback_path.read_text(encoding="utf-8"))
            self.assertEqual(fallback["policy"], "continue_with_baseline_layoutcompile")


if __name__ == "__main__":
    unittest.main()
