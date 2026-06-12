import json

import pytest
from PIL import Image

from app.config import Config, OmniParserConfig, OCRConfig, PlannerConfig, ServerConfig, VLMConfig
from app.omniparser import Detection
from app.pipeline import Pipeline
from app.schema import BBox, CandidateClassification, TextBlock


class FakePipeline(Pipeline):
    def __init__(self, texts, detections, classifications, errors=None):
        config = Config(
            ocr=OCRConfig(token="fake"),
            omniparser=OmniParserConfig(model_path=""),
            vlm=VLMConfig(api_key="fake"),
            planner=PlannerConfig(),
            server=ServerConfig(),
        )
        super().__init__(config)
        self._texts = texts
        self._detections = detections
        self._classifications = classifications
        self._errors = errors or {}

    async def _run_ocr_stage(self, image_path):
        error = self._errors.get("ocr", "")
        return ([] if error else self._texts), error

    async def _run_omni_stage(self, image):
        error = self._errors.get("omni", "")
        return ([] if error else self._detections), error

    async def _run_vlm_stage(self, image, candidates, batches, texts, raw_dir):
        errors = self._errors.get("vlm", [])
        return ([] if errors else self._classifications), errors


@pytest.mark.asyncio
async def test_pipeline_ocr_only_degrades_without_omni_or_vlm(tmp_path):
    image_path = tmp_path / "input.png"
    Image.new("RGB", (120, 120), "white").save(image_path)
    pipeline = FakePipeline(
        texts=[TextBlock("text_0001", "Hello", BBox(10, 10, 40, 20), 0.99)],
        detections=[],
        classifications=[],
        errors={"omni": "model missing", "vlm": ["vlm_api_key_missing"]},
    )

    dsl = await pipeline.run(str(image_path), str(tmp_path / "compile"), "task_fake")

    children = dsl["root"]["children"]
    assert len(children) == 1
    assert children[0]["type"] == "text"
    assert children[0]["text"]["characters"] == "Hello"
    summary = json.loads((tmp_path / "compile/report/pipeline_summary.v1.json").read_text())
    assert summary["provider_error_count"] == 2
    assert (tmp_path / "compile/evidence/omni_error.v1.json").exists()


@pytest.mark.asyncio
async def test_pipeline_emits_image_asset_and_shape_without_shape_asset(tmp_path):
    image_path = tmp_path / "input.png"
    Image.new("RGB", (220, 220), "white").save(image_path)
    pipeline = FakePipeline(
        texts=[],
        detections=[
            Detection(20, 20, 40, 40, 0.95),
            Detection(80, 20, 100, 40, 0.90),
        ],
        classifications=[
            CandidateClassification("cand_0001", "icon", "image", "emit", 0.9, "icon"),
            CandidateClassification("cand_0002", "card_bg", "shape", "emit", 0.9, "card"),
        ],
    )

    dsl = await pipeline.run(str(image_path), str(tmp_path / "compile"), "task_fake")

    children = dsl["root"]["children"]
    assert [child["type"] for child in children] == ["shape", "image"]
    assert len(dsl["assets"]) == 1
    assert (tmp_path / "compile/assets/node_image_0001.png").exists()
    assert not (tmp_path / "compile/assets/node_shape_0002.png").exists()
