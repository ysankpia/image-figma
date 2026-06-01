from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


ElementType = Literal["text", "image", "shape"]
ClassificationKind = Literal["image", "shape", "suppress"]


@dataclass(frozen=True)
class BBox:
    x: int
    y: int
    width: int
    height: int

    @property
    def area(self) -> int:
        return max(0, self.width) * max(0, self.height)

    @property
    def x2(self) -> int:
        return self.x + self.width

    @property
    def y2(self) -> int:
        return self.y + self.height

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


@dataclass(frozen=True)
class TextBlock:
    id: str
    text: str
    bbox: BBox
    confidence: float
    source: str = "ocr"

    @property
    def x(self) -> int:
        return self.bbox.x

    @property
    def y(self) -> int:
        return self.bbox.y

    @property
    def width(self) -> int:
        return self.bbox.width

    @property
    def height(self) -> int:
        return self.bbox.height


@dataclass(frozen=True)
class ObjectCandidate:
    id: str
    bbox: BBox
    confidence: float
    source: str = "omniparser"
    area: int = 0
    overlaps_text: bool = False
    text_overlap_ratio: float = 0.0
    text_block_count: int = 0


@dataclass(frozen=True)
class CandidateBatch:
    id: str
    bbox: BBox
    candidate_ids: list[str]


@dataclass(frozen=True)
class CandidateClassification:
    candidate_id: str
    role: str
    kind: ClassificationKind
    decision: str
    confidence: float
    reason: str
    source: str = "vlm"


@dataclass(frozen=True)
class DraftElement:
    id: str
    type: ElementType
    role: str
    bbox: BBox
    z: int
    confidence: float
    source_ids: list[str]
    decision_reason: str
    text: str = ""
    style: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PromotionDecision:
    candidate_id: str
    decision: str
    reason: str
    emitted_element_id: str = ""
    role: str = ""
    kind: str = ""
    confidence: float = 0.0


def dataclass_to_dict(value: Any) -> Any:
    if isinstance(value, list):
        return [dataclass_to_dict(item) for item in value]
    if isinstance(value, dict):
        return {key: dataclass_to_dict(item) for key, item in value.items()}
    if hasattr(value, "__dataclass_fields__"):
        return {key: dataclass_to_dict(item) for key, item in asdict(value).items()}
    return value
