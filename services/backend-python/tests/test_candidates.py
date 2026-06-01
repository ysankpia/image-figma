from app.candidates import build_candidate_batches, build_candidates
from app.omniparser import Detection
from app.schema import BBox, TextBlock


def test_build_candidates_clamps_dedupes_and_tracks_text_overlap():
    detections = [
        Detection(x=-5, y=10, width=30, height=30, confidence=0.9),
        Detection(x=-4, y=11, width=30, height=30, confidence=0.8),
        Detection(x=100, y=100, width=3, height=30, confidence=0.95),
    ]
    texts = [TextBlock(id="text_0001", text="Hello", bbox=BBox(0, 20, 20, 10), confidence=0.99)]

    candidates = build_candidates(detections, texts, 200, 200)

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.id == "cand_0001"
    assert candidate.bbox == BBox(0, 10, 25, 30)
    assert candidate.overlaps_text is True
    assert candidate.text_block_count == 1
    assert candidate.text_overlap_ratio > 0


def test_build_candidate_batches_respects_hard_cap():
    candidates = [
        _candidate(i, y=i * 8)
        for i in range(1, 61)
    ]

    batches = build_candidate_batches(candidates, 400, 1200, hard_cap=25)

    assert batches
    assert all(len(batch.candidate_ids) <= 25 for batch in batches)
    assert sorted(id for batch in batches for id in batch.candidate_ids) == [c.id for c in candidates]


def _candidate(index: int, y: int):
    from app.schema import ObjectCandidate

    box = BBox(10, y, 20, 20)
    return ObjectCandidate(
        id=f"cand_{index:04d}",
        bbox=box,
        confidence=0.9,
        area=box.area,
    )
