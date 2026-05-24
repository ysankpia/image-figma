from __future__ import annotations

from typing import Any

from .types import OwnershipDecision


def build_routing_views(decisions: list[OwnershipDecision]) -> dict[str, Any]:
    return {
        "textOwnedEvidenceIds": [item.id for item in decisions if item.ownership == "text_owned"],
        "visualFormingEvidenceIds": [item.id for item in decisions if item.allowed_for_object_forming_visual_side],
        "auditOnlyEvidenceIds": [item.id for item in decisions if item.ownership == "audit_only"],
        "mixedOrUncertainEvidenceIds": [item.id for item in decisions if item.ownership == "mixed_or_uncertain"],
        "textOverlayOnVisualEvidenceIds": [item.id for item in decisions if item.ownership_reason_kind == "image_with_text_overlay"],
        "bySourceVisualEvidenceItemId": {
            item.source_visual_evidence_item_id: {
                "ownershipDecisionId": item.id,
                "allowedForObjectFormingVisualSide": item.allowed_for_object_forming_visual_side,
                "allowedForTextSide": item.allowed_for_text_side,
                "suppressedAsVisual": item.suppressed_as_visual,
                "ownership": item.ownership,
                "decision": item.decision,
                "ownershipReasonKind": item.ownership_reason_kind,
                "matchedTextBoxIds": item.matched_text_box_ids,
                "textPreview": item.text_preview,
                **({"sourceLineage": item.source_lineage} if item.source_lineage is not None else {}),
            }
            for item in decisions
            if item.source_visual_evidence_item_id
        },
        "byTextBoxId": {
            item.source_text_box_id: {
                "ownershipDecisionId": item.id,
                "allowedForTextSide": item.allowed_for_text_side,
                "ownership": item.ownership,
                "decision": item.decision,
                "textPreview": item.text_preview,
            }
            for item in decisions
            if item.source_text_box_id
        },
    }

def build_audit(decisions: list[OwnershipDecision]) -> list[dict[str, Any]]:
    return [
        {
            "id": f"audit_{index + 1:04d}",
            "ownershipDecisionId": item.id,
            "source": item.source,
            "sourceEvidenceId": item.source_evidence_id,
            "sourceVisualEvidenceItemId": item.source_visual_evidence_item_id,
            "sourceTextBoxId": item.source_text_box_id,
            "ownership": item.ownership,
            "decision": item.decision,
            "ownershipReasonKind": item.ownership_reason_kind,
            "matchedTextBoxIds": item.matched_text_box_ids,
            "suppressedAsVisual": item.suppressed_as_visual,
            "allowedForObjectFormingVisualSide": item.allowed_for_object_forming_visual_side,
            "allowedForTextSide": item.allowed_for_text_side,
            "risks": item.risks,
            "reasons": item.reasons,
            **({"sourceLineage": item.source_lineage} if item.source_lineage is not None else {}),
        }
        for index, item in enumerate(decisions)
    ]
