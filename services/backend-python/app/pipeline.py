from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import orjson
from PIL import Image

from .artifacts import error_payload, write_json
from .candidates import build_candidate_batches, build_candidates
from .config import Config
from .crop import crop_image_assets
from .dsl import build_dsl
from .ocr import run_ocr
from .omniparser import Detection, OmniParser
from .planner import promote_elements
from .schema import CandidateClassification, ObjectCandidate, TextBlock
from .spatial import clamp_bbox
from .vlm import classify_candidates


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
        output = Path(output_dir)
        evidence_dir = output / "evidence"
        report_dir = output / "report"
        raw_vlm_dir = evidence_dir / "raw_vlm_response"
        draft_dir = output / "draft"
        output.mkdir(parents=True, exist_ok=True)

        image = Image.open(image_path).convert("RGB")
        img_w, img_h = image.size

        texts, ocr_error = await self._run_ocr_stage(image_path)
        texts = normalize_texts(texts, img_w, img_h)
        if ocr_error:
            write_json(evidence_dir / "ocr_error.v1.json", error_payload("ocr", ocr_error))
        write_json(evidence_dir / "ocr_blocks.v1.json", {"version": "ocr_blocks.v1", "blocks": texts})

        detections, omni_error = await self._run_omni_stage(image)
        if omni_error:
            write_json(evidence_dir / "omni_error.v1.json", error_payload("omniparser", omni_error))

        candidates = build_candidates(detections, texts, img_w, img_h)
        write_json(
            evidence_dir / "omni_candidates.v1.json",
            {"version": "omni_candidates.v1", "candidates": candidates},
        )

        batches = build_candidate_batches(
            candidates,
            img_w,
            img_h,
            hard_cap=self.config.planner.batch_max_candidates,
        )
        write_json(
            evidence_dir / "candidate_batches.v1.json",
            {"version": "candidate_batches.v1", "batches": batches},
        )

        classifications, vlm_errors = await self._run_vlm_stage(image, candidates, batches, texts, raw_vlm_dir)
        write_json(
            evidence_dir / "vlm_classifications.v1.json",
            {
                "version": "vlm_classifications.v1",
                "classifications": classifications,
                "errors": vlm_errors,
            },
        )

        promotion = promote_elements(
            image=image,
            texts=texts,
            candidates=candidates,
            classifications=classifications,
            config=self.config.planner,
            vlm_available=not vlm_errors,
        )
        write_json(
            evidence_dir / "promotion_decisions.v1.json",
            {
                "version": "promotion_decisions.v1",
                "decisions": promotion.decisions,
                "elements": promotion.elements,
            },
        )

        asset_map = crop_image_assets(image, promotion.elements, output_dir)
        dsl = build_dsl(promotion.elements, asset_map, image, task_id)
        draft_dir.mkdir(parents=True, exist_ok=True)
        dsl_path = draft_dir / "draft_runtime.dsl.v1_0.json"
        dsl_path.write_bytes(orjson.dumps(dsl, option=orjson.OPT_INDENT_2))

        summary = build_summary(
            texts=texts,
            candidates=candidates,
            classifications=classifications,
            elements=promotion.elements,
            asset_count=len(asset_map),
            ocr_error=ocr_error,
            omni_error=omni_error,
            vlm_errors=vlm_errors,
            decisions=[decision.reason for decision in promotion.decisions],
        )
        write_json(report_dir / "pipeline_summary.v1.json", summary)
        return dsl

    async def _run_ocr_stage(self, image_path: str) -> tuple[list[TextBlock], str]:
        try:
            return await run_ocr(image_path, self.config.ocr), ""
        except Exception as exc:
            return [], str(exc)

    async def _run_omni_stage(self, image: Image.Image) -> tuple[list[Detection], str]:
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._run_omniparser, image), ""
        except Exception as exc:
            return [], str(exc)

    async def _run_vlm_stage(
        self,
        image: Image.Image,
        candidates: list[ObjectCandidate],
        batches: list,
        texts: list[TextBlock],
        raw_dir: Path,
    ) -> tuple[list[CandidateClassification], list[str]]:
        try:
            result = await classify_candidates(
                image=image,
                candidates=candidates,
                batches=batches,
                texts=texts,
                config=self.config.vlm,
                raw_dir=raw_dir,
            )
            return result.classifications, result.errors
        except Exception as exc:
            return [], [str(exc)]

    def _run_omniparser(self, image: Image.Image) -> list[Detection]:
        if self.omniparser is None:
            return []
        return self.omniparser.detect(image)


def build_summary(
    texts: list[TextBlock],
    candidates: list[ObjectCandidate],
    classifications: list[CandidateClassification],
    elements: list,
    asset_count: int,
    ocr_error: str,
    omni_error: str,
    vlm_errors: list[str],
    decisions: list[str],
) -> dict[str, Any]:
    emitted_text = sum(1 for element in elements if element.type == "text")
    emitted_image = sum(1 for element in elements if element.type == "image")
    emitted_shape = sum(1 for element in elements if element.type == "shape")
    tiny_images = sum(1 for element in elements if element.type == "image" and element.bbox.area < 400)
    text_overlap_images = sum(
        1 for element in elements
        if element.type == "image"
        for candidate in candidates
        if candidate.id in element.source_ids and candidate.text_overlap_ratio > 0.08
    )
    suppressed: dict[str, int] = {}
    for reason in decisions:
        if reason.startswith("suppress"):
            suppressed[reason] = suppressed.get(reason, 0) + 1
    return {
        "version": "pipeline_summary.v1",
        "ocr_text_count": len(texts),
        "omni_candidate_count": len(candidates),
        "vlm_classified_count": len(classifications),
        "emitted_text_count": emitted_text,
        "emitted_image_count": emitted_image,
        "emitted_shape_count": emitted_shape,
        "suppressed_count_by_reason": suppressed,
        "asset_count": asset_count,
        "tiny_image_count": tiny_images,
        "text_overlap_image_count": text_overlap_images,
        "provider_error_count": int(bool(ocr_error)) + int(bool(omni_error)) + len(vlm_errors),
        "errors": {
            "ocr": ocr_error,
            "omniparser": omni_error,
            "vlm": vlm_errors,
        },
    }


def normalize_texts(texts: list[TextBlock], page_width: int, page_height: int) -> list[TextBlock]:
    out: list[TextBlock] = []
    for text in texts:
        cleaned = text.text.strip()
        if not cleaned:
            continue
        box = clamp_bbox(text.bbox, page_width, page_height)
        if box is None or box.width <= 1 or box.height < 6:
            continue
        out.append(
            TextBlock(
                id=text.id,
                text=cleaned,
                bbox=box,
                confidence=text.confidence,
                source=text.source,
            )
        )
    return out
