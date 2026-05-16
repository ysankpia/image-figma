from __future__ import annotations

import base64
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from openai import OpenAI

from .config import Settings
from .dsl_factory import DslRegionAsset
from .png_tools import PngMetadata


PrimitiveKind = Literal[
    "region",
    "card",
    "button_background",
    "image",
    "icon",
    "shape",
    "divider",
    "text_block",
    "unknown",
]
PrimitiveStatus = Literal["completed", "partial", "failed", "skipped"]

ALLOWED_KINDS: set[str] = {
    "region",
    "card",
    "button_background",
    "image",
    "icon",
    "shape",
    "divider",
    "text_block",
    "unknown",
}


@dataclass(frozen=True)
class PrimitiveRegionInput:
    id: str
    path: str
    x: int
    y: int
    width: int
    height: int


@dataclass
class VisualPrimitive:
    id: str
    kind: PrimitiveKind
    label: str
    bbox: list[int]
    confidence: float
    sourceRegionId: str | None = None
    source: str = "fake"


@dataclass
class VisualPrimitiveRelation:
    type: str
    parentId: str
    childId: str
    confidence: float = 1


@dataclass
class VisualPrimitiveWarning:
    code: str
    message: str
    primitiveId: str | None = None


@dataclass
class VisualPrimitiveDocument:
    version: str
    taskId: str
    provider: str
    model: str | None
    imageSize: dict[str, int]
    coordinateSpace: Literal["pixel"]
    primitives: list[VisualPrimitive]
    relations: list[VisualPrimitiveRelation]
    warnings: list[VisualPrimitiveWarning]
    meta: dict[str, Any] = field(default_factory=dict)
    status: PrimitiveStatus = "completed"
    error: dict[str, str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_fake_primitive_document(
    *,
    task_id: str,
    image: PngMetadata,
    regions: list[DslRegionAsset],
) -> VisualPrimitiveDocument:
    if regions:
        primitives = [
            VisualPrimitive(
                id=f"vp_region_{region.name}",
                kind="region",
                label=f"{region.name.title()} fallback region",
                bbox=[region.x, region.y, region.width, region.height],
                confidence=1,
                sourceRegionId=region.name,
                source="fake",
            )
            for region in regions
        ]
    else:
        primitives = [
            VisualPrimitive(
                id="vp_region_full_image",
                kind="region",
                label="Full image fallback region",
                bbox=[0, 0, image.width, image.height],
                confidence=1,
                sourceRegionId="full_image",
                source="fake",
            )
        ]

    return VisualPrimitiveDocument(
        version="0.1",
        taskId=task_id,
        provider="fake",
        model=None,
        imageSize={"width": image.width, "height": image.height},
        coordinateSpace="pixel",
        primitives=primitives,
        relations=[],
        warnings=[],
        meta={"notes": "visual_primitive_contract_harness"},
    )


def build_failed_primitive_document(
    *,
    task_id: str,
    image: PngMetadata,
    provider: str,
    model: str | None,
    code: str,
    message: str,
) -> VisualPrimitiveDocument:
    return VisualPrimitiveDocument(
        version="0.1",
        taskId=task_id,
        provider=provider,
        model=model,
        imageSize={"width": image.width, "height": image.height},
        coordinateSpace="pixel",
        primitives=[],
        relations=[],
        warnings=[VisualPrimitiveWarning(code=code, message=message)],
        meta={"notes": "visual_primitive_contract_harness"},
        status="failed",
        error={"code": code, "message": message},
    )


def extract_visual_primitives(
    *,
    task_id: str,
    image: PngMetadata,
    regions: list[DslRegionAsset],
    region_inputs: list[PrimitiveRegionInput],
    settings: Settings,
) -> VisualPrimitiveDocument:
    provider = settings.visual_primitive_provider
    if provider == "fake":
        return build_fake_primitive_document(task_id=task_id, image=image, regions=regions)
    if provider == "openai":
        return extract_openai_visual_primitives(
            task_id=task_id,
            image=image,
            region_inputs=region_inputs,
            settings=settings,
        )
    return build_failed_primitive_document(
        task_id=task_id,
        image=image,
        provider=provider,
        model=None,
        code="UNSUPPORTED_PRIMITIVE_PROVIDER",
        message=f"Unsupported visual primitive provider: {provider}.",
    )


def extract_openai_visual_primitives(
    *,
    task_id: str,
    image: PngMetadata,
    region_inputs: list[PrimitiveRegionInput],
    settings: Settings,
) -> VisualPrimitiveDocument:
    if not settings.openai_api_key:
        return build_failed_primitive_document(
            task_id=task_id,
            image=image,
            provider="openai",
            model=settings.openai_vision_model,
            code="OPENAI_API_KEY_MISSING",
            message="OPENAI_API_KEY is required when VISUAL_PRIMITIVE_PROVIDER=openai.",
        )

    primitives: list[VisualPrimitive] = []
    warnings: list[VisualPrimitiveWarning] = []
    client = OpenAI(api_key=settings.openai_api_key, timeout=settings.openai_timeout_seconds)
    for region in region_inputs[:3]:
        try:
            payload = call_openai_region_extractor(client, settings.openai_vision_model, region)
            region_primitives, region_warnings = normalize_openai_region_payload(
                payload=payload,
                region=region,
                image=image,
            )
            if not region_primitives:
                region_warnings.append(
                    VisualPrimitiveWarning(
                        code="OPENAI_EMPTY_REGION_RESULT",
                        message=f"{region.id}: no primitives returned.",
                    )
                )
            primitives.extend(region_primitives)
            warnings.extend(region_warnings)
        except Exception as error:
            warnings.append(
                VisualPrimitiveWarning(
                    code="OPENAI_REGION_EXTRACTION_FAILED",
                    message=f"{region.id}: {error}",
                )
            )

    status_value: PrimitiveStatus = "completed"
    if warnings and primitives:
        status_value = "partial"
    elif warnings and not primitives:
        status_value = "failed"

    document = VisualPrimitiveDocument(
        version="0.1",
        taskId=task_id,
        provider="openai",
        model=settings.openai_vision_model,
        imageSize={"width": image.width, "height": image.height},
        coordinateSpace="pixel",
        primitives=primitives,
        relations=[],
        warnings=warnings,
        meta={"notes": "visual_primitive_contract_harness"},
        status=status_value,
    )
    if status_value == "failed":
        document.error = {
            "code": "PRIMITIVE_EXTRACTION_FAILED",
            "message": "OpenAI visual primitive extraction failed for all regions.",
        }
    return validate_primitive_document(document)


def call_openai_region_extractor(client: OpenAI, model: str, region: PrimitiveRegionInput) -> dict[str, Any]:
    image_data = base64.b64encode(Path(region.path).read_bytes()).decode("ascii")
    response = client.responses.create(
        model=model,
        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": build_openai_prompt(region),
                    },
                    {
                        "type": "input_image",
                        "image_url": f"data:image/png;base64,{image_data}",
                    },
                ],
            }
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "visual_primitives",
                "schema": openai_primitive_schema(),
                "description": "Non-text UI visual primitive candidates for one screenshot region.",
                "strict": True,
            }
        },
    )
    text = response.output_text
    return json.loads(text)


def build_openai_prompt(region: PrimitiveRegionInput) -> str:
    return (
        "Extract non-text UI visual primitives from this UI screenshot region. "
        "Do not output DesignDSL. Do not transcribe full text; OCR will handle text later. "
        "Return cards, button backgrounds, icons, images, shapes, dividers, tab/nav/list item regions. "
        "Coordinates must be region-local normalized boxes [x1,y1,x2,y2] where every value is an integer from 0 to 999. "
        f"The region id is {region.id}, with pixel size {region.width}x{region.height}."
    )


def openai_primitive_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "primitives": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "id": {"type": "string"},
                        "kind": {"type": "string", "enum": sorted(ALLOWED_KINDS - {"region"})},
                        "label": {"type": "string"},
                        "box": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "minItems": 4,
                            "maxItems": 4,
                        },
                        "confidence": {"type": "number"},
                    },
                    "required": ["id", "kind", "label", "box", "confidence"],
                },
            }
        },
        "required": ["primitives"],
    }


def normalize_openai_region_payload(
    *,
    payload: dict[str, Any],
    region: PrimitiveRegionInput,
    image: PngMetadata,
) -> tuple[list[VisualPrimitive], list[VisualPrimitiveWarning]]:
    primitives: list[VisualPrimitive] = []
    warnings: list[VisualPrimitiveWarning] = []
    for item in payload.get("primitives", []):
        primitive_id = f"vp_{region.id}_{str(item.get('id', 'unknown')).strip()}"
        box = item.get("box")
        if not isinstance(box, list) or len(box) != 4:
            warnings.append(VisualPrimitiveWarning(code="INVALID_NORMALIZED_BOX", message="Box must have four values."))
            continue
        pixel_bbox, box_warnings = normalized_box_to_pixel_bbox(box, region, image)
        warnings.extend(box_warnings)
        if pixel_bbox is None:
            continue
        kind = item.get("kind") if item.get("kind") in ALLOWED_KINDS else "unknown"
        primitives.append(
            VisualPrimitive(
                id=primitive_id,
                kind=kind,  # type: ignore[arg-type]
                label=str(item.get("label") or kind),
                bbox=pixel_bbox,
                confidence=clamp_float(item.get("confidence"), 0, 1),
                sourceRegionId=region.id,
                source="openai",
            )
        )
    return primitives, warnings


def normalized_box_to_pixel_bbox(
    box: list[Any],
    region: PrimitiveRegionInput,
    image: PngMetadata,
) -> tuple[list[int] | None, list[VisualPrimitiveWarning]]:
    warnings: list[VisualPrimitiveWarning] = []
    try:
        x1, y1, x2, y2 = [float(value) for value in box]
    except (TypeError, ValueError):
        return None, [VisualPrimitiveWarning(code="INVALID_NORMALIZED_BOX", message="Box contains non-numeric values.")]
    if x2 <= x1 or y2 <= y1:
        return None, [VisualPrimitiveWarning(code="INVALID_NORMALIZED_BOX", message="Box has non-positive size.")]
    original = [x1, y1, x2, y2]
    x1 = clamp_float(x1, 0, 999)
    y1 = clamp_float(y1, 0, 999)
    x2 = clamp_float(x2, 0, 999)
    y2 = clamp_float(y2, 0, 999)
    if original != [x1, y1, x2, y2]:
        warnings.append(VisualPrimitiveWarning(code="BOX_CLAMPED", message="Normalized box was clamped to 0..999."))

    pixel_x1 = region.x + round((x1 / 999) * region.width)
    pixel_y1 = region.y + round((y1 / 999) * region.height)
    pixel_x2 = region.x + round((x2 / 999) * region.width)
    pixel_y2 = region.y + round((y2 / 999) * region.height)
    pixel_x1 = clamp_int(pixel_x1, 0, image.width)
    pixel_y1 = clamp_int(pixel_y1, 0, image.height)
    pixel_x2 = clamp_int(pixel_x2, 0, image.width)
    pixel_y2 = clamp_int(pixel_y2, 0, image.height)
    width = pixel_x2 - pixel_x1
    height = pixel_y2 - pixel_y1
    if width <= 1 or height <= 1:
        return None, [VisualPrimitiveWarning(code="PRIMITIVE_TOO_SMALL", message="Primitive bbox is too small.")]
    return [pixel_x1, pixel_y1, width, height], warnings


def validate_primitive_document(document: VisualPrimitiveDocument) -> VisualPrimitiveDocument:
    image_width = int(document.imageSize.get("width", 0) or 0)
    image_height = int(document.imageSize.get("height", 0) or 0)
    seen: set[str] = set()
    primitives: list[VisualPrimitive] = []
    warnings = list(document.warnings)
    for primitive in document.primitives:
        if primitive.kind not in ALLOWED_KINDS:
            warnings.append(
                VisualPrimitiveWarning(
                    code="INVALID_PRIMITIVE_KIND",
                    message=f"Primitive kind downgraded to unknown: {primitive.kind}.",
                    primitiveId=primitive.id,
                )
            )
            primitive.kind = "unknown"
        if primitive.id in seen:
            warnings.append(
                VisualPrimitiveWarning(
                    code="DUPLICATE_PRIMITIVE_ID",
                    message=f"Duplicate primitive id dropped: {primitive.id}.",
                    primitiveId=primitive.id,
                )
            )
            continue
        bbox, bbox_warnings = normalize_primitive_bbox(
            primitive_id=primitive.id,
            bbox=primitive.bbox,
            image_width=image_width,
            image_height=image_height,
        )
        warnings.extend(bbox_warnings)
        if bbox is None:
            continue
        seen.add(primitive.id)
        primitive.bbox = bbox
        primitive.confidence = clamp_float(primitive.confidence, 0, 1)
        primitives.append(primitive)

    relation_primitives = {primitive.id for primitive in primitives}
    relations: list[VisualPrimitiveRelation] = []
    for relation in document.relations:
        if relation.parentId not in relation_primitives or relation.childId not in relation_primitives:
            warnings.append(
                VisualPrimitiveWarning(
                    code="INVALID_RELATION_REF",
                    message=f"Invalid relation dropped: {relation.parentId}->{relation.childId}.",
                )
            )
            continue
        relation.confidence = clamp_float(relation.confidence, 0, 1)
        relations.append(relation)

    document.primitives = primitives
    document.relations = relations
    document.warnings = warnings
    return document


def normalize_primitive_bbox(
    *,
    primitive_id: str,
    bbox: list[int],
    image_width: int,
    image_height: int,
) -> tuple[list[int] | None, list[VisualPrimitiveWarning]]:
    if image_width <= 0 or image_height <= 0:
        return None, [
            VisualPrimitiveWarning(
                code="INVALID_IMAGE_SIZE",
                message="Primitive document image size is invalid.",
                primitiveId=primitive_id,
            )
        ]
    if not isinstance(bbox, list) or len(bbox) != 4:
        return None, [
            VisualPrimitiveWarning(
                code="INVALID_PRIMITIVE_BBOX",
                message="Primitive bbox must be [x, y, width, height].",
                primitiveId=primitive_id,
            )
        ]
    try:
        x, y, width, height = [float(value) for value in bbox]
    except (TypeError, ValueError):
        return None, [
            VisualPrimitiveWarning(
                code="INVALID_PRIMITIVE_BBOX",
                message="Primitive bbox contains non-numeric values.",
                primitiveId=primitive_id,
            )
        ]

    if width <= 1 or height <= 1:
        return None, [
            VisualPrimitiveWarning(
                code="INVALID_PRIMITIVE_BBOX",
                message="Primitive bbox has non-positive size.",
                primitiveId=primitive_id,
            )
        ]

    x1 = round(x)
    y1 = round(y)
    x2 = round(x + width)
    y2 = round(y + height)
    if x2 <= 0 or y2 <= 0 or x1 >= image_width or y1 >= image_height:
        return None, [
            VisualPrimitiveWarning(
                code="PRIMITIVE_BBOX_OUT_OF_BOUNDS",
                message="Primitive bbox does not intersect image bounds.",
                primitiveId=primitive_id,
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
            VisualPrimitiveWarning(
                code="PRIMITIVE_TOO_SMALL",
                message="Primitive bbox is too small after clamping.",
                primitiveId=primitive_id,
            )
        ]

    warnings: list[VisualPrimitiveWarning] = []
    normalized = [clamped_x1, clamped_y1, clamped_width, clamped_height]
    if normalized != [x1, y1, x2 - x1, y2 - y1]:
        warnings.append(
            VisualPrimitiveWarning(
                code="PRIMITIVE_BBOX_CLAMPED",
                message="Primitive bbox was clamped to image bounds.",
                primitiveId=primitive_id,
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
