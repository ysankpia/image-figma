from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import orjson
from PIL import Image

from .config import Config
from .crop import crop_elements
from .dsl import build_dsl
from .merge import merge_results
from .ocr import run_ocr
from .omniparser import OmniParser
from .vlm import run_vlm


class Pipeline:
    def __init__(self, config: Config) -> None:
        self.config = config
        self._omniparser: OmniParser | None = None

    @property
    def omniparser(self) -> OmniParser | None:
        if self._omniparser is None and self.config.omniparser.model_path:
            self._omniparser = OmniParser(self.config.omniparser)
        return self._omniparser

    async def run(self, image_path: str, output_dir: str, task_id: str) -> dict[str, Any]:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        image = Image.open(image_path).convert("RGB")
        img_w, img_h = image.size

        # Run three detectors in parallel
        ocr_task = asyncio.create_task(run_ocr(image_path, self.config.ocr))
        vlm_task = asyncio.create_task(run_vlm(image_path, (img_w, img_h), self.config.vlm))

        # OmniParser is sync (ONNX), run in thread
        loop = asyncio.get_event_loop()
        omni_task = loop.run_in_executor(None, self._run_omniparser, image)

        texts, vlm_elements, detections = await asyncio.gather(
            ocr_task, vlm_task, omni_task
        )

        # Merge
        elements = merge_results(
            texts=texts,
            detections=detections,
            vlm_elements=vlm_elements,
            page_width=img_w,
            page_height=img_h,
        )

        # Crop
        asset_map = crop_elements(image, elements, output_dir)

        # Build DSL
        dsl = build_dsl(elements, asset_map, image, task_id)

        # Write DSL
        dsl_dir = Path(output_dir) / "draft"
        dsl_dir.mkdir(parents=True, exist_ok=True)
        dsl_path = dsl_dir / "draft_runtime.dsl.v1_0.json"
        dsl_path.write_bytes(orjson.dumps(dsl, option=orjson.OPT_INDENT_2))

        return dsl

    def _run_omniparser(self, image: Image.Image):
        if self.omniparser is None:
            return []
        return self.omniparser.detect(image)
