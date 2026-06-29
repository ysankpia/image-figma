from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from ui_rebuilder.cli import main
from ui_rebuilder.io import read_json


class PipelineTest(unittest.TestCase):
    def test_offline_pipeline_creates_resumable_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.png"
            run_dir = root / "run"
            _make_source(source)

            exit_code = main(["run", "--input", str(source), "--out", str(run_dir), "--mock-qwen"])

            self.assertEqual(exit_code, 0)
            self.assertTrue((run_dir / "run.json").exists())
            self.assertTrue((run_dir / "asset_plan.json").exists())
            self.assertTrue((run_dir / "sheet_manifest.json").exists())
            self.assertTrue((run_dir / "qwen_manifest.json").exists())
            self.assertTrue((run_dir / "asset_manifest.json").exists())
            self.assertTrue((run_dir / "preview.html").exists())
            self.assertTrue((run_dir / "report.md").exists())

            plan = read_json(run_dir / "asset_plan.json")
            sheets = read_json(run_dir / "sheet_manifest.json")
            assets = read_json(run_dir / "asset_manifest.json")
            self.assertGreaterEqual(len(plan["rois"]), 3)
            self.assertGreaterEqual(len(sheets["sheets"]), 1)
            self.assertGreaterEqual(assets["summary"]["originalCropCount"], len(plan["rois"]))

    def test_full_page_qwen_mock_is_resumable(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.png"
            run_dir = root / "run"
            _make_source(source)

            exit_code = main(
                [
                    "run",
                    "--input",
                    str(source),
                    "--out",
                    str(run_dir),
                    "--mock-qwen",
                    "--full-page-qwen",
                    "--skip-sheet-qwen",
                ]
            )

            self.assertEqual(exit_code, 0)
            self.assertTrue((run_dir / "qwen_full_manifest.json").exists())
            self.assertTrue((run_dir / "work/qwen_full/full_page/layer_00.png").exists())
            assets = read_json(run_dir / "asset_manifest.json")
            self.assertIn("qwenFullComponentCount", assets["summary"])


def _make_source(path: Path) -> None:
    image = Image.new("RGB", (360, 780), "#eef7ff")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((12, 80, 348, 130), radius=24, fill="white")
    draw.rounded_rectangle((0, 150, 360, 340), radius=0, fill="#9fdcff")
    draw.ellipse((220, 190, 310, 280), fill="#7a4df3")
    draw.rounded_rectangle((14, 350, 346, 445), radius=18, fill="white")
    for index in range(5):
        x = 38 + index * 60
        draw.ellipse((x, 370, x + 32, 402), fill=(240 - index * 20, 100, 120 + index * 18))
    draw.rounded_rectangle((14, 470, 346, 650), radius=18, fill="white")
    for index in range(3):
        y = 492 + index * 48
        draw.ellipse((34, y, 72, y + 38), fill=(120, 160 + index * 20, 230))
        draw.rounded_rectangle((250, y + 6, 320, y + 34), radius=14, fill="#7b46f6")
    image.save(path)


if __name__ == "__main__":
    unittest.main()
