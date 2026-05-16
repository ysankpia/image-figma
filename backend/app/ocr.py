from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from .config import Settings
from .png_tools import PngMetadata


OCRStatus = Literal["completed", "partial", "failed", "skipped"]


@dataclass
class OCRBlock:
    id: str
    text: str
    bbox: list[int]
    confidence: float
    lineId: str
    blockId: str
    source: str = "fake"


@dataclass
class OCRWarning:
    code: str
    message: str
    blockId: str | None = None


@dataclass
class OCRDocument:
    version: str
    taskId: str
    provider: str
    model: str | None
    imageSize: dict[str, int]
    coordinateSpace: Literal["pixel"]
    blocks: list[OCRBlock]
    warnings: list[OCRWarning]
    meta: dict[str, Any] = field(default_factory=dict)
    status: OCRStatus = "completed"
    error: dict[str, str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def extract_ocr(
    *,
    task_id: str,
    image: PngMetadata,
    settings: Settings,
    source_path: Path | None = None,
) -> OCRDocument:
    provider = settings.ocr_provider
    if provider == "fake":
        return build_fake_ocr_document(task_id=task_id, image=image)
    if provider == "baidu_ppocrv5":
        from .ocr_baidu import extract_baidu_ppocrv5

        return extract_baidu_ppocrv5(
            task_id=task_id,
            image=image,
            source_path=source_path,
            settings=settings,
        )
    return build_failed_ocr_document(
        task_id=task_id,
        image=image,
        provider=provider,
        model=None,
        code="UNSUPPORTED_OCR_PROVIDER",
        message=f"Unsupported OCR provider: {provider}.",
    )


def build_fake_ocr_document(*, task_id: str, image: PngMetadata) -> OCRDocument:
    blocks = fake_blocks_for_image(image)
    document = OCRDocument(
        version="0.1",
        taskId=task_id,
        provider="fake",
        model=None,
        imageSize={"width": image.width, "height": image.height},
        coordinateSpace="pixel",
        blocks=blocks,
        warnings=[],
        meta={"notes": "ocr_contract_harness"},
    )
    return validate_ocr_document(document)


def build_failed_ocr_document(
    *,
    task_id: str,
    image: PngMetadata,
    provider: str,
    model: str | None,
    code: str,
    message: str,
) -> OCRDocument:
    return OCRDocument(
        version="0.1",
        taskId=task_id,
        provider=provider,
        model=model,
        imageSize={"width": image.width, "height": image.height},
        coordinateSpace="pixel",
        blocks=[],
        warnings=[OCRWarning(code=code, message=message)],
        meta={"notes": "ocr_contract_harness"},
        status="failed",
        error={"code": code, "message": message},
    )


def fake_blocks_for_image(image: PngMetadata) -> list[OCRBlock]:
    width = image.width
    height = image.height
    if width <= 0 or height <= 0:
        return []

    first_width = max(24, min(width - 20, round(width * 0.45)))
    second_width = max(24, min(width - 20, round(width * 0.6)))
    first_height = max(12, min(36, round(height * 0.025)))
    second_height = max(12, min(32, round(height * 0.018)))
    left = min(max(16, round(width * 0.08)), max(0, width - first_width))
    top = min(max(16, round(height * 0.04)), max(0, height - first_height))
    second_top = min(top + first_height + 12, max(0, height - second_height))

    return [
        OCRBlock(
            id="ocr_text_001",
            text="Sample title",
            bbox=[left, top, first_width, first_height],
            confidence=0.96,
            lineId="line_001",
            blockId="block_001",
        ),
        OCRBlock(
            id="ocr_text_002",
            text="Sample description",
            bbox=[left, second_top, second_width, second_height],
            confidence=0.9,
            lineId="line_002",
            blockId="block_002",
        ),
    ]


def validate_ocr_document(document: OCRDocument) -> OCRDocument:
    image_width = int(document.imageSize.get("width", 0) or 0)
    image_height = int(document.imageSize.get("height", 0) or 0)
    seen: set[str] = set()
    blocks: list[OCRBlock] = []
    warnings = list(document.warnings)

    for block in document.blocks:
        if block.id in seen:
            warnings.append(
                OCRWarning(
                    code="DUPLICATE_OCR_BLOCK_ID",
                    message=f"Duplicate OCR block id dropped: {block.id}.",
                    blockId=block.id,
                )
            )
            continue
        if not block.text.strip():
            warnings.append(
                OCRWarning(
                    code="OCR_TEXT_EMPTY",
                    message="OCR text block was dropped because text is empty.",
                    blockId=block.id,
                )
            )
            continue
        bbox, bbox_warnings = normalize_ocr_bbox(
            block_id=block.id,
            bbox=block.bbox,
            image_width=image_width,
            image_height=image_height,
        )
        warnings.extend(bbox_warnings)
        if bbox is None:
            continue
        seen.add(block.id)
        block.text = block.text.strip()
        block.bbox = bbox
        block.confidence = clamp_float(block.confidence, 0, 1)
        blocks.append(block)

    document.blocks = blocks
    document.warnings = warnings
    return document


def normalize_ocr_bbox(
    *,
    block_id: str,
    bbox: list[int],
    image_width: int,
    image_height: int,
) -> tuple[list[int] | None, list[OCRWarning]]:
    if image_width <= 0 or image_height <= 0:
        return None, [
            OCRWarning(
                code="INVALID_IMAGE_SIZE",
                message="OCR document image size is invalid.",
                blockId=block_id,
            )
        ]
    if not isinstance(bbox, list) or len(bbox) != 4:
        return None, [
            OCRWarning(
                code="INVALID_OCR_BBOX",
                message="OCR bbox must be [x, y, width, height].",
                blockId=block_id,
            )
        ]
    try:
        x, y, width, height = [float(value) for value in bbox]
    except (TypeError, ValueError):
        return None, [
            OCRWarning(
                code="INVALID_OCR_BBOX",
                message="OCR bbox contains non-numeric values.",
                blockId=block_id,
            )
        ]
    if width <= 1 or height <= 1:
        return None, [
            OCRWarning(
                code="INVALID_OCR_BBOX",
                message="OCR bbox has non-positive size.",
                blockId=block_id,
            )
        ]

    x1 = round(x)
    y1 = round(y)
    x2 = round(x + width)
    y2 = round(y + height)
    if x2 <= 0 or y2 <= 0 or x1 >= image_width or y1 >= image_height:
        return None, [
            OCRWarning(
                code="OCR_BBOX_OUT_OF_BOUNDS",
                message="OCR bbox does not intersect image bounds.",
                blockId=block_id,
            )
        ]

    clamped_x1 = clamp_int(x1, 0, image_width)
    clamped_y1 = clamp_int(y1, 0, image_height)
    clamped_x2 = clamp_int(x2, 0, image_width)
    clamped_y2 = clamp_int(y2, 0, image_height)
    clamped_width = clamped_x2 - clamped_x1
    clamped_height = clamped_y2 - clamped_y1
    if clamped_width <= 1 or clamped_height <= 1:
        return None, [
            OCRWarning(
                code="OCR_BBOX_TOO_SMALL",
                message="OCR bbox is too small after clamping.",
                blockId=block_id,
            )
        ]

    normalized = [clamped_x1, clamped_y1, clamped_width, clamped_height]
    warnings: list[OCRWarning] = []
    if normalized != [x1, y1, x2 - x1, y2 - y1]:
        warnings.append(
            OCRWarning(
                code="OCR_BBOX_CLAMPED",
                message="OCR bbox was clamped to image bounds.",
                blockId=block_id,
            )
        )
    return normalized, warnings


def clamp_float(value: Any, minimum: float, maximum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = minimum
    return max(minimum, min(maximum, number))


def clamp_int(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))
