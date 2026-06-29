from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from py_m29_locator import OUTPUT_NAME, locate  # noqa: E402


class LocatorTest(unittest.TestCase):
    def test_writes_location_json_and_crops(self) -> None:
        with TemporaryDirectory() as tmp_raw:
            tmp = Path(tmp_raw)
            input_path = tmp / "input.png"
            image = Image.new("RGBA", (80, 60), (255, 255, 255, 255))
            draw = ImageDraw.Draw(image)
            draw.rectangle((10, 12, 29, 25), fill=(0, 0, 0, 255))
            image.save(input_path)

            output_dir = tmp / "out"
            doc = locate(input_path, output_dir)

            self.assertEqual(doc["schemaName"], "M29Locations")
            self.assertEqual(len(doc["items"]), 1)
            self.assertEqual(doc["items"][0]["bbox"], {"x": 10, "y": 12, "width": 20, "height": 14})
            self.assertEqual(doc["items"][0]["cropPath"], "crops/loc_0001.png")
            self.assertTrue((output_dir / "crops" / "loc_0001.png").exists())
            with Image.open(output_dir / "crops" / "loc_0001.png") as crop:
                self.assertEqual(crop.size, (20, 14))

            disk_doc = json.loads((output_dir / OUTPUT_NAME).read_text(encoding="utf-8"))
            self.assertEqual(disk_doc["items"][0]["bbox"], {"x": 10, "y": 12, "width": 20, "height": 14})


if __name__ == "__main__":
    unittest.main()
