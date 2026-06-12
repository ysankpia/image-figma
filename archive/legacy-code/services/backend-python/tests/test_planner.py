from PIL import Image

from app.config import PlannerConfig
from app.planner import promote_elements
from app.schema import BBox, CandidateClassification, ObjectCandidate, TextBlock


def test_promote_elements_keeps_ocr_text_as_authority():
    image = Image.new("RGB", (200, 200), "white")
    texts = [TextBlock(id="text_0001", text="Pay", bbox=BBox(10, 10, 40, 20), confidence=0.99)]

    result = promote_elements(image, texts, [], [], PlannerConfig(), vlm_available=False)

    assert len(result.elements) == 1
    assert result.elements[0].type == "text"
    assert result.elements[0].text == "Pay"


def test_promote_elements_accepts_valid_image_candidate():
    image = Image.new("RGB", (300, 300), "white")
    candidate = _candidate("cand_0001", BBox(30, 30, 40, 40), text_overlap=0)
    classification = CandidateClassification(
        candidate_id="cand_0001",
        role="icon",
        kind="image",
        decision="emit",
        confidence=0.9,
        reason="visible icon",
    )

    result = promote_elements(image, [], [candidate], [classification], PlannerConfig(), vlm_available=True)

    images = [element for element in result.elements if element.type == "image"]
    assert len(images) == 1
    assert result.decisions[0].decision == "emit_image"


def test_promote_elements_rejects_tiny_and_text_overlap_images():
    image = Image.new("RGB", (300, 300), "white")
    tiny = _candidate("cand_0001", BBox(10, 10, 8, 8), text_overlap=0)
    overlap = _candidate("cand_0002", BBox(50, 50, 40, 40), text_overlap=0.5)
    classifications = [
        _classification("cand_0001", "icon", "image"),
        _classification("cand_0002", "thumbnail", "image"),
    ]

    result = promote_elements(image, [], [tiny, overlap], classifications, PlannerConfig(), vlm_available=True)

    assert [decision.reason for decision in result.decisions] == [
        "suppress_too_small",
        "suppress_text_overlap",
    ]
    assert not [element for element in result.elements if element.type == "image"]


def test_promote_elements_allows_large_raster_with_internal_text():
    image = Image.new("RGB", (500, 1000), "white")
    texts = [
        TextBlock(id="text_0001", text="Sale", bbox=BBox(30, 130, 60, 20), confidence=0.99),
        TextBlock(id="text_0002", text="$99", bbox=BBox(300, 420, 80, 24), confidence=0.99),
        TextBlock(id="text_0003", text="New", bbox=BBox(340, 140, 40, 18), confidence=0.99),
    ]
    candidate = ObjectCandidate(
        id="cand_0001",
        bbox=BBox(20, 100, 400, 360),
        confidence=0.9,
        area=144000,
        overlaps_text=True,
        text_overlap_ratio=0.03,
        text_block_count=3,
    )

    result = promote_elements(
        image,
        texts,
        [candidate],
        [_classification("cand_0001", "photo", "image")],
        PlannerConfig(),
        vlm_available=True,
    )

    images = [element for element in result.elements if element.type == "image"]
    assert len(images) == 1
    assert images[0].bbox == candidate.bbox
    assert images[0].decision_reason == "emit_image_with_internal_text"


def test_promote_elements_rejects_high_overlap_raster_text():
    image = Image.new("RGB", (300, 300), "white")
    candidate = ObjectCandidate(
        id="cand_0001",
        bbox=BBox(20, 20, 160, 90),
        confidence=0.9,
        area=14400,
        overlaps_text=True,
        text_overlap_ratio=0.35,
        text_block_count=2,
    )

    result = promote_elements(
        image,
        [],
        [candidate],
        [_classification("cand_0001", "thumbnail", "image")],
        PlannerConfig(),
        vlm_available=True,
    )

    assert result.decisions[0].reason == "suppress_contains_text"
    assert not [element for element in result.elements if element.type == "image"]


def test_promote_elements_repairs_image_role_shape_kind():
    image = Image.new("RGB", (300, 300), "white")
    candidate = _candidate("cand_0001", BBox(40, 40, 80, 80), text_overlap=0)

    result = promote_elements(
        image,
        [],
        [candidate],
        [_classification("cand_0001", "icon", "shape")],
        PlannerConfig(),
        vlm_available=True,
    )

    images = [element for element in result.elements if element.type == "image"]
    assert len(images) == 1
    assert images[0].decision_reason == "emit_image_kind_repaired"


def test_promote_elements_clips_edge_label_from_icon_candidate():
    image = Image.new("RGB", (240, 240), "white")
    text = TextBlock(id="text_0001", text="Home", bbox=BBox(60, 125, 60, 20), confidence=0.99)
    candidate = ObjectCandidate(
        id="cand_0001",
        bbox=BBox(50, 50, 90, 100),
        confidence=0.9,
        area=9000,
        overlaps_text=True,
        text_overlap_ratio=0.14,
        text_block_count=1,
    )
    classification = CandidateClassification(
        candidate_id="cand_0001",
        role="icon",
        kind="image",
        decision="suppress",
        confidence=0.9,
        reason="candidate merges icon and label",
    )

    result = promote_elements(
        image,
        [text],
        [candidate],
        [classification],
        PlannerConfig(),
        vlm_available=True,
    )

    images = [element for element in result.elements if element.type == "image"]
    assert len(images) == 1
    assert images[0].bbox == BBox(50, 50, 90, 75)
    assert images[0].decision_reason == "emit_image_text_clipped"


def test_promote_elements_recovers_compact_unknown_visual_candidate():
    image = Image.new("RGB", (240, 240), "white")
    text = TextBlock(id="text_0001", text="Label", bbox=BBox(70, 125, 50, 20), confidence=0.99)
    candidate = ObjectCandidate(
        id="cand_0001",
        bbox=BBox(50, 50, 90, 100),
        confidence=0.9,
        area=9000,
        overlaps_text=True,
        text_overlap_ratio=0.12,
        text_block_count=1,
    )

    result = promote_elements(
        image,
        [text],
        [candidate],
        [_classification("cand_0001", "unknown", "suppress")],
        PlannerConfig(),
        vlm_available=True,
    )

    images = [element for element in result.elements if element.type == "image"]
    assert len(images) == 1
    assert images[0].bbox == BBox(50, 50, 90, 75)
    assert images[0].decision_reason == "emit_image_unknown_text_clipped"


def test_promote_elements_keeps_text_role_suppressed():
    image = Image.new("RGB", (300, 300), "white")
    candidate = _candidate("cand_0001", BBox(20, 20, 160, 30), text_overlap=0.4)

    result = promote_elements(
        image,
        [],
        [candidate],
        [_classification("cand_0001", "text", "suppress")],
        PlannerConfig(),
        vlm_available=True,
    )

    assert result.decisions[0].reason == "suppress_unknown_role"
    assert not [element for element in result.elements if element.type == "image"]


def test_promote_elements_rejects_large_unknown_container():
    image = Image.new("RGB", (600, 1200), "white")
    candidate = ObjectCandidate(
        id="cand_0001",
        bbox=BBox(30, 200, 540, 220),
        confidence=0.9,
        area=118800,
        overlaps_text=True,
        text_overlap_ratio=0.12,
        text_block_count=3,
    )

    result = promote_elements(
        image,
        [],
        [candidate],
        [_classification("cand_0001", "unknown", "suppress")],
        PlannerConfig(),
        vlm_available=True,
    )

    assert result.decisions[0].reason == "suppress_unknown_role"
    assert not [element for element in result.elements if element.type == "image"]


def test_promote_elements_accepts_shape_and_divider():
    image = Image.new("RGB", (400, 400), "white")
    card = _candidate("cand_0001", BBox(10, 10, 200, 80), text_overlap=0)
    divider = _candidate("cand_0002", BBox(10, 120, 160, 2), text_overlap=0)
    classifications = [
        _classification("cand_0001", "card_bg", "shape"),
        _classification("cand_0002", "divider", "shape"),
    ]

    result = promote_elements(image, [], [card, divider], classifications, PlannerConfig(), vlm_available=True)

    assert [element.type for element in result.elements] == ["shape", "shape"]
    assert [decision.decision for decision in result.decisions] == ["emit_shape", "emit_shape"]


def _candidate(candidate_id: str, box: BBox, text_overlap: float):
    return ObjectCandidate(
        id=candidate_id,
        bbox=box,
        confidence=0.9,
        area=box.area,
        overlaps_text=text_overlap > 0,
        text_overlap_ratio=text_overlap,
        text_block_count=1 if text_overlap > 0 else 0,
    )


def _classification(candidate_id: str, role: str, kind: str):
    return CandidateClassification(
        candidate_id=candidate_id,
        role=role,
        kind=kind,
        decision="emit",
        confidence=0.9,
        reason="ok",
    )
