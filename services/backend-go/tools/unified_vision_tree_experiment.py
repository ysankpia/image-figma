#!/usr/bin/env python3
"""Unified Vision tree contract experiment.

This is an isolated Python harness for the next research step after Go flat v1.
It does not feed product runtime and does not replace layoutcompile output.

Two modes are supported:

1. Offline validation:
   python3 unified_vision_tree_experiment.py --input unified_vision_input.v1.json \
     --result candidate.json --out validation.json

2. Provider experiment:
   python3 unified_vision_tree_experiment.py --input unified_vision_input.v1.json \
     --image source.png --result-out tree_result.json --validation-out validation.json
"""

from __future__ import annotations

import argparse
import base64
import http.client
import io
import json
import os
import sys
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any


RESULT_VERSION = "unified_vision_tree_result.v1"
VALIDATION_VERSION = "unified_vision_tree_validation.v1"
TRANSIENT_PROVIDER_STATUS = {408, 409, 425, 429, 500, 502, 503, 504, 520, 522, 524}

PHYSICAL_REJECTION_CODES = {
    "required_size_overflow",
    "actual_gap_too_large",
    "gap_too_large",
    "gap_variance_high",
    "cross_axis_spread_high",
}


@dataclass
class Options:
    min_confidence: float = 0.70
    max_fit_ratio: float = 1.01
    max_gap: int = 96
    max_gap_variance: int = 4096
    max_cross_spread_factor: float = 1.60
    transport_retries: int = 3
    repair_attempts: int = 1
    timeout_seconds: float = 180
    temperature: float = 0
    concurrency: int = 3


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run or validate the Unified Vision tree experiment.")
    parser.add_argument("--input", required=True, help="unified_vision_input.v1.json")
    parser.add_argument("--image", default="", help="source PNG path, required for provider mode")
    parser.add_argument("--result", default="", help="candidate unified_vision_tree_result.v1 JSON to validate")
    parser.add_argument("--out", default="", help="validation output JSON, kept for validate-only compatibility")
    parser.add_argument("--result-out", default="", help="provider result output JSON")
    parser.add_argument("--validation-out", default="", help="validation output JSON")
    parser.add_argument("--workdir", default="", help="raw/error artifact directory")
    parser.add_argument("--fixture-response", default="", help="test-only raw provider response for every batch")
    args = parser.parse_args(argv)

    input_path = Path(args.input)
    input_doc = json.loads(input_path.read_text(encoding="utf-8"))
    options = options_from_env()

    validation_out = Path(args.validation_out or args.out or input_path.with_name("unified_vision_tree_validation.v1.json"))
    result_out = Path(args.result_out or input_path.with_name("unified_vision_tree_result.v1.json"))
    workdir = Path(args.workdir or result_out.parent)

    if args.result:
        result = json.loads(Path(args.result).read_text(encoding="utf-8"))
        validation = validate_tree(input_doc, result, options)
        write_json(validation_out, validation)
        return 0 if validation["summary"]["errorCount"] == 0 else 1

    if not args.image:
        print("--image is required when --result is not provided", file=sys.stderr)
        return 2

    result = run_provider_experiment(input_doc, Path(args.image), workdir, options, args.fixture_response)
    validation = validate_tree(input_doc, result, options)
    write_json(result_out, result)
    write_json(validation_out, validation)
    return 0


def options_from_env() -> Options:
    return Options(
        min_confidence=float(env_first(("UNIFIED_VISION_MIN_CONFIDENCE",), "0.70")),
        max_fit_ratio=float(env_first(("UNIFIED_VISION_MAX_FIT_RATIO",), "1.01")),
        max_gap=int(env_first(("UNIFIED_VISION_MAX_GAP",), "96")),
        max_gap_variance=int(env_first(("UNIFIED_VISION_MAX_GAP_VARIANCE",), "4096")),
        max_cross_spread_factor=float(env_first(("UNIFIED_VISION_MAX_Y_SPREAD_FACTOR",), "1.60")),
        transport_retries=int(env_first(("UNIFIED_VISION_TRANSPORT_RETRIES",), "3")),
        repair_attempts=int(env_first(("UNIFIED_VISION_REPAIR_ATTEMPTS",), "1")),
        timeout_seconds=float(env_first(("UNIFIED_VISION_TIMEOUT_SECONDS",), "180")),
        temperature=float(env_first(("UNIFIED_VISION_TEMPERATURE",), "0") or 0),
        concurrency=int(env_first(("UNIFIED_VISION_TREE_CONCURRENCY", "UNIFIED_VISION_CONCURRENCY"), "3")),
    )


def run_provider_experiment(input_doc: dict[str, Any], image_path: Path, workdir: Path, options: Options, fixture_response: str = "") -> dict[str, Any]:
    workdir.mkdir(parents=True, exist_ok=True)
    input_batches = list(input_doc.get("batches", []))
    batches: list[dict[str, Any] | None] = [None] * len(input_batches)
    if options.concurrency <= 1 or len(input_batches) <= 1 or fixture_response:
        for index, batch in enumerate(input_batches):
            batches[index] = run_batch(input_doc, batch, image_path, workdir, options, fixture_response)
    else:
        with ThreadPoolExecutor(max_workers=max(1, options.concurrency)) as executor:
            futures = {
                executor.submit(run_batch, input_doc, batch, image_path, workdir, options, fixture_response): index
                for index, batch in enumerate(input_batches)
            }
            for future in as_completed(futures):
                batches[futures[future]] = future.result()
    return {
        "version": RESULT_VERSION,
        "generatedAt": timestamp(),
        "batches": [batch for batch in batches if batch is not None],
        "warnings": [],
    }


def run_batch(input_doc: dict[str, Any], batch: dict[str, Any], image_path: Path, workdir: Path, options: Options, fixture_response: str = "") -> dict[str, Any]:
    batch_id = str(batch.get("id") or "")
    section_id = str(batch.get("sectionId") or "")
    image_data_url = "" if fixture_response else crop_data_url(image_path, rect(batch.get("cropBBox") or batch.get("sectionBBox") or {}))
    previous_raw = ""
    previous_validation: dict[str, Any] | None = None
    max_semantic_attempts = 1 + max(0, options.repair_attempts)

    for semantic_attempt in range(max_semantic_attempts):
        repair_attempt = semantic_attempt > 0
        started = time.time()
        try:
            prompt = tree_prompt(input_doc, batch, previous_raw, previous_validation)
            if fixture_response:
                raw = Path(fixture_response).read_text(encoding="utf-8")
            else:
                raw = call_provider(prompt, image_data_url, options)
            raw_path = write_text(workdir / f"{safe_name(batch_id)}_attempt_{semantic_attempt + 1}.raw.txt", raw)
            model_result = parse_result_text(raw)
            validate_result_shape(model_result)
            candidate = aggregate_single_batch(input_doc, batch, model_result, repair_attempt, raw_path, started)
            validation = validate_tree(input_doc, candidate, options)
            batch_validation = validation_for_batch(validation, batch_id)
            if not batch_validation or batch_validation.get("rejectedNodeCount", 0) == 0:
                return candidate["batches"][0]
            previous_raw = raw
            previous_validation = validation
            if not should_repair_batch(validation, batch_id):
                return candidate["batches"][0]
            if semantic_attempt >= max_semantic_attempts - 1:
                return candidate["batches"][0]
        except Exception as exc:  # noqa: BLE001 - experiment must preserve batch fallback artifacts.
            error_path = write_text(workdir / f"{safe_name(batch_id)}_attempt_{semantic_attempt + 1}.error.txt", str(exc))
            if semantic_attempt < max_semantic_attempts - 1:
                previous_raw = previous_raw or str(exc)
                previous_validation = {
                    "rejectedNodes": [
                        {
                            "batchId": batch_id,
                            "groupId": "",
                            "reason": "parse_or_provider_error",
                            "message": str(exc),
                        }
                    ]
                }
                continue
            return {
                "batchId": batch_id,
                "sectionId": section_id,
                "attempt": semantic_attempt + 1,
                "result": {},
                "errorArtifact": str(error_path),
                "error": str(exc),
                "repairAttempt": repair_attempt,
                "durationMillis": int((time.time() - started) * 1000),
            }

    return {
        "batchId": batch_id,
        "sectionId": section_id,
        "attempt": max_semantic_attempts,
        "result": {},
        "error": "unreachable_batch_state",
    }


def aggregate_single_batch(input_doc: dict[str, Any], batch: dict[str, Any], model_result: dict[str, Any], repair_attempt: bool, raw_path: Path, started: float) -> dict[str, Any]:
    return {
        "version": RESULT_VERSION,
        "generatedAt": timestamp(),
        "batches": [
            {
                "batchId": batch.get("id"),
                "sectionId": batch.get("sectionId"),
                "attempt": 2 if repair_attempt else 1,
                "result": model_result,
                "rawArtifact": str(raw_path),
                "repairAttempt": repair_attempt,
                "durationMillis": int((time.time() - started) * 1000),
            }
        ],
        "warnings": [],
    }


def validate_result_shape(result: dict[str, Any]) -> None:
    if result.get("version") != RESULT_VERSION:
        raise RuntimeError(f"expected {RESULT_VERSION}, got {result.get('version')!r}")
    if not isinstance(result.get("nodes"), list):
        raise RuntimeError("nodes must be a list")
    if "roots" in result and not isinstance(result.get("roots"), list):
        raise RuntimeError("roots must be a list")
    if "ungrouped" in result and not isinstance(result.get("ungrouped"), list):
        raise RuntimeError("ungrouped must be a list")


def validate_tree(input_doc: dict[str, Any], result: dict[str, Any], options: Options | None = None) -> dict[str, Any]:
    options = options or Options()
    batches_by_id = {str(batch.get("id")): batch for batch in input_doc.get("batches", [])}
    total_evidence = {
        item["id"]
        for batch in input_doc.get("batches", [])
        for item in batch.get("evidence", [])
        if item.get("id")
    }
    aggregate = new_validation(input_doc, result)

    if result.get("version") != RESULT_VERSION:
        aggregate["rejectedNodes"].append(rejected("", "", "bad_version", f"expected {RESULT_VERSION}"))
        aggregate["summary"] = summarize(aggregate, total_evidence)
        return aggregate

    result_batches = result.get("batches")
    if isinstance(result_batches, list):
        seen_batches = set()
        for batch_result in result_batches:
            batch_id = str(batch_result.get("batchId") or "")
            seen_batches.add(batch_id)
            batch = batches_by_id.get(batch_id)
            if not batch:
                aggregate["batches"].append(batch_validation(batch_id, "", fallback=True, reason="unknown_batch_id"))
                continue
            if batch_result.get("error"):
                aggregate["batches"].append(
                    batch_validation(
                        batch_id,
                        str(batch.get("sectionId") or ""),
                        fallback=True,
                        reason=str(batch_result.get("error")),
                        repair_attempted=bool(batch_result.get("repairAttempt")),
                    )
                )
                continue
            merge_batch_validation(aggregate, validate_batch(batch, batch_result.get("result") or {}, options, bool(batch_result.get("repairAttempt"))))
        for batch_id, batch in batches_by_id.items():
            if batch_id not in seen_batches:
                aggregate["batches"].append(batch_validation(batch_id, str(batch.get("sectionId") or ""), fallback=True, reason="missing_model_result"))
    else:
        batches = list(batches_by_id.values())
        if not batches:
            aggregate["rejectedNodes"].append(rejected("", "", "missing_input_batch", "input has no batches"))
        elif len(batches) > 1:
            aggregate["rejectedNodes"].append(rejected("", "", "ambiguous_single_batch_result", "aggregate result must contain batches"))
        else:
            merge_batch_validation(aggregate, validate_batch(batches[0], result, options, False))

    aggregate["summary"] = summarize(aggregate, total_evidence)
    return aggregate


def validate_batch(batch: dict[str, Any], model_result: dict[str, Any], options: Options, repair_attempted: bool) -> dict[str, Any]:
    batch_id = str(batch.get("id") or "")
    section_id = str(batch.get("sectionId") or "")
    evidence_by_id = {str(item.get("id")): item for item in batch.get("evidence", []) if item.get("id")}
    local = {
        "batches": [],
        "acceptedNodes": [],
        "rejectedNodes": [],
        "ignoredNodes": [],
    }
    node_errors: dict[str, list[str]] = defaultdict(list)
    global_errors: list[dict[str, Any]] = []

    if model_result.get("version") != RESULT_VERSION:
        global_errors.append(rejected(batch_id, "", "bad_result_version", str(model_result.get("version"))))
    nodes = model_result.get("nodes")
    if not isinstance(nodes, list):
        nodes = []
        global_errors.append(rejected(batch_id, "", "nodes_not_array", "nodes must be an array"))
    roots = model_result.get("roots")
    roots_provided = isinstance(roots, list) and bool(roots)
    if not isinstance(roots, list):
        roots = []

    node_by_id: dict[str, dict[str, Any]] = {}
    duplicate_ids = set()
    for index, node in enumerate(nodes):
        if not isinstance(node, dict):
            global_errors.append(rejected(batch_id, "", "node_not_object", f"nodes[{index}]"))
            continue
        node_id = str(node.get("id") or "").strip()
        if not node_id:
            global_errors.append(rejected(batch_id, "", "empty_group_id", f"nodes[{index}]"))
            continue
        if node_id in node_by_id:
            duplicate_ids.add(node_id)
            node_errors[node_id].append("duplicate_group_id")
            continue
        node_by_id[node_id] = node

    group_parent_count: Counter[str] = Counter()
    direct_leaf_owner: dict[str, str] = {}
    for root_id in roots:
        root_id = str(root_id)
        if root_id not in node_by_id:
            global_errors.append(rejected(batch_id, root_id, "unknown_root_ref", root_id))
    for node_id, node in node_by_id.items():
        direction = str(node.get("direction") or "").strip().lower()
        if direction not in ("horizontal", "vertical"):
            node_errors[node_id].append("bad_direction")
        confidence = as_float(node.get("confidence"), 0)
        low_confidence = confidence < options.min_confidence
        if confidence < options.min_confidence:
            node_errors[node_id].append(f"ignored_low_confidence:{confidence:.3f}")
        gap = as_int(node.get("gap"), 0)
        if gap < 0:
            node_errors[node_id].append("negative_gap")
        if gap > options.max_gap:
            node_errors[node_id].append(f"gap_too_large:{gap}")
        children = node.get("children")
        if not isinstance(children, list):
            node_errors[node_id].append("children_not_array")
            continue
        if len(children) == 0:
            node_errors[node_id].append("zero_child_group")
        if len(children) == 1:
            node_errors[node_id].append("one_child_group")
        for child_ref in children:
            child_id = str(child_ref)
            if child_id == node_id:
                node_errors[node_id].append("self_reference")
            if child_id in evidence_by_id:
                if not low_confidence:
                    previous = direct_leaf_owner.get(child_id)
                    if previous and previous != node_id:
                        node_errors[node_id].append(f"duplicate_leaf_owner:{child_id}:{previous}")
                    direct_leaf_owner[child_id] = node_id
                continue
            if child_id in node_by_id:
                group_parent_count[child_id] += 1
                continue
            node_errors[node_id].append(f"unknown_child_ref:{child_id}")

    for group_id, count in group_parent_count.items():
        if count > 1:
            node_errors[group_id].append(f"multi_parent_group:{count}")
    if not roots_provided:
        roots = inferred_roots(node_by_id, group_parent_count)
    else:
        roots = normalized_roots(roots, node_by_id, group_parent_count)

    mark_cycles(node_by_id, node_errors)

    accepted_cache: dict[str, dict[str, Any] | None] = {}

    def accept_node(node_id: str) -> dict[str, Any] | None:
        if node_id in accepted_cache:
            return accepted_cache[node_id]
        node = node_by_id.get(node_id)
        if not node:
            return None
        if node_errors.get(node_id):
            accepted_cache[node_id] = None
            return None
        children = [str(value) for value in node.get("children", [])]
        child_boxes = []
        leaf_ids: set[str] = set()
        normalized_children = []
        for child_id in children:
            if child_id in evidence_by_id:
                child_boxes.append(rect(evidence_by_id[child_id].get("bbox") or {}))
                leaf_ids.add(child_id)
                normalized_children.append(child_id)
                continue
            child_accepted = accept_node(child_id)
            if not child_accepted:
                node_errors[node_id].append(f"invalid_child_group:{child_id}")
                accepted_cache[node_id] = None
                return None
            child_boxes.append(child_accepted["bbox"])
            leaf_ids.update(child_accepted["leafEvidenceIds"])
            normalized_children.append(child_id)
        direction = str(node.get("direction") or "").strip().lower()
        gap = as_int(node.get("gap"), 0)
        metrics = group_metrics(child_boxes, direction, gap)
        if metrics["fitRatio"] > options.max_fit_ratio:
            node_errors[node_id].append(f"required_size_overflow:{metrics['fitRatio']:.3f}")
        if metrics["medianCross"] > 0 and metrics["crossSpread"] > metrics["medianCross"] * options.max_cross_spread_factor:
            node_errors[node_id].append("cross_axis_spread_high")
        if metrics["maxGap"] > options.max_gap:
            node_errors[node_id].append(f"actual_gap_too_large:{metrics['maxGap']}")
        if metrics["gapVariance"] > options.max_gap_variance:
            node_errors[node_id].append(f"gap_variance_high:{metrics['gapVariance']}")
        if node_errors.get(node_id):
            accepted_cache[node_id] = None
            return None
        accepted = {
            "batchId": batch_id,
            "sectionId": section_id,
            "groupId": node_id,
            "name": str(node.get("name") or ""),
            "direction": direction,
            "children": normalized_children,
            "leafEvidenceIds": sorted(leaf_ids),
            "bbox": metrics["bbox"],
            "gap": gap,
            "requiredSize": metrics["requiredSize"],
            "fitRatio": metrics["fitRatio"],
            "crossSpread": metrics["crossSpread"],
            "medianCross": metrics["medianCross"],
            "maxGap": metrics["maxGap"],
            "gapVariance": metrics["gapVariance"],
            "confidence": as_float(node.get("confidence"), 0),
            "reason": str(node.get("reason") or ""),
        }
        accepted_cache[node_id] = accepted
        return accepted

    for node_id in sorted(node_by_id):
        accepted = accept_node(node_id)
        if accepted:
            local["acceptedNodes"].append(accepted)

    rejected_ids = sorted(node_id for node_id, reasons in node_errors.items() if reasons)
    for node_id in rejected_ids:
        for reason in unique(node_errors[node_id]):
            if reason.startswith("ignored_low_confidence:"):
                local["ignoredNodes"].append(ignored(batch_id, node_id, reason))
                continue
            local["rejectedNodes"].append(rejected(batch_id, node_id, reason, reason))
    local["rejectedNodes"].extend(global_errors)

    local["batches"].append(
        batch_validation(
            batch_id,
            section_id,
            accepted_count=len(local["acceptedNodes"]),
            rejected_count=len(local["rejectedNodes"]),
            repair_attempted=repair_attempted,
            reason=rejection_summary(local["rejectedNodes"]),
        )
    )
    return local


def inferred_roots(node_by_id: dict[str, dict[str, Any]], group_parent_count: Counter[str]) -> list[str]:
    return sorted(node_id for node_id in node_by_id if group_parent_count.get(node_id, 0) == 0)


def normalized_roots(roots: list[Any], node_by_id: dict[str, dict[str, Any]], group_parent_count: Counter[str]) -> list[str]:
    normalized = []
    seen = set()
    for root_id in roots:
        root_id = str(root_id)
        if root_id in node_by_id and group_parent_count.get(root_id, 0) == 0 and root_id not in seen:
            normalized.append(root_id)
            seen.add(root_id)
    for root_id in inferred_roots(node_by_id, group_parent_count):
        if root_id not in seen:
            normalized.append(root_id)
            seen.add(root_id)
    return normalized


def mark_cycles(node_by_id: dict[str, dict[str, Any]], node_errors: dict[str, list[str]]) -> None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_id: str, stack: list[str]) -> None:
        if node_id in visiting:
            cycle = stack[stack.index(node_id) :] if node_id in stack else [node_id]
            for group_id in cycle:
                node_errors[group_id].append("cycle")
            return
        if node_id in visited:
            return
        visiting.add(node_id)
        node = node_by_id.get(node_id) or {}
        for child_ref in node.get("children") or []:
            child_id = str(child_ref)
            if child_id in node_by_id:
                visit(child_id, stack + [child_id])
        visiting.remove(node_id)
        visited.add(node_id)

    for node_id in sorted(node_by_id):
        visit(node_id, [node_id])


def group_metrics(boxes: list[dict[str, int]], direction: str, expected_gap: int) -> dict[str, Any]:
    clean = [box for box in boxes if not rect_empty(box)]
    if not clean:
        return {
            "bbox": {"x": 0, "y": 0, "width": 0, "height": 0},
            "requiredSize": 0,
            "fitRatio": 0,
            "crossSpread": 0,
            "medianCross": 0,
            "maxGap": 0,
            "gapVariance": 0,
        }
    if direction == "vertical":
        clean.sort(key=lambda box: (box["y"], box["x"], box["width"], box["height"]))
        primary_size = "height"
        primary_start = "y"
        primary_end = rect_bottom
        cross_size = "width"
        cross_start = "x"
    else:
        clean.sort(key=lambda box: (box["x"], box["y"], box["width"], box["height"]))
        primary_size = "width"
        primary_start = "x"
        primary_end = rect_right
        cross_size = "height"
        cross_start = "y"
    bbox = union_rects(clean)
    required = max(0, expected_gap) * max(0, len(clean) - 1) + sum(box[primary_size] for box in clean)
    gaps = []
    for index in range(1, len(clean)):
        gap = clean[index][primary_start] - primary_end(clean[index - 1])
        if gap > 0:
            gaps.append(gap)
    container_size = bbox[primary_size]
    cross_positions = [box[cross_start] for box in clean]
    cross_sizes = [box[cross_size] for box in clean if box[cross_size] > 0]
    return {
        "bbox": bbox,
        "requiredSize": required,
        "fitRatio": float(required) / float(container_size) if container_size > 0 else 0,
        "crossSpread": max(cross_positions) - min(cross_positions) if cross_positions else 0,
        "medianCross": median(cross_sizes),
        "maxGap": max(gaps) if gaps else 0,
        "gapVariance": variance(gaps),
    }


def new_validation(input_doc: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    return {
        "version": VALIDATION_VERSION,
        "generatedAt": timestamp(),
        "inputVersion": input_doc.get("version"),
        "resultVersion": result.get("version"),
        "batches": [],
        "acceptedNodes": [],
        "rejectedNodes": [],
        "ignoredNodes": [],
        "summary": {},
    }


def merge_batch_validation(aggregate: dict[str, Any], local: dict[str, Any]) -> None:
    aggregate["batches"].extend(local.get("batches", []))
    aggregate["acceptedNodes"].extend(local.get("acceptedNodes", []))
    aggregate["rejectedNodes"].extend(local.get("rejectedNodes", []))
    aggregate.setdefault("ignoredNodes", []).extend(local.get("ignoredNodes", []))


def batch_validation(
    batch_id: str,
    section_id: str,
    accepted_count: int = 0,
    rejected_count: int = 0,
    fallback: bool = False,
    reason: str = "",
    repair_attempted: bool = False,
) -> dict[str, Any]:
    return {
        "batchId": batch_id,
        "sectionId": section_id,
        "acceptedNodeCount": accepted_count,
        "rejectedNodeCount": rejected_count,
        "fallback": fallback,
        "reason": reason,
        "repairAttempted": repair_attempted,
    }


def rejected(batch_id: str, group_id: str, reason: str, message: str) -> dict[str, Any]:
    return {
        "batchId": batch_id,
        "groupId": group_id,
        "reason": reason,
        "message": message,
    }


def ignored(batch_id: str, group_id: str, reason: str) -> dict[str, Any]:
    return {
        "batchId": batch_id,
        "groupId": group_id,
        "reason": reason,
    }


def summarize(validation: dict[str, Any], total_evidence: set[str]) -> dict[str, Any]:
    accepted_leaf_ids = {
        leaf_id
        for node in validation.get("acceptedNodes", [])
        for leaf_id in node.get("leafEvidenceIds", [])
    }
    reason_counts = Counter(str(item.get("reason", "")).split(":", 1)[0] for item in validation.get("rejectedNodes", []))
    fallback_batches = [batch for batch in validation.get("batches", []) if batch.get("fallback")]
    repair_attempts = [batch for batch in validation.get("batches", []) if batch.get("repairAttempted")]
    provider_errors = [batch for batch in fallback_batches if batch.get("reason")]
    physical = sum(reason_counts.get(code, 0) for code in PHYSICAL_REJECTION_CODES)
    return {
        "batchCount": len(validation.get("batches", [])),
        "acceptedNodeCount": len(validation.get("acceptedNodes", [])),
        "rejectedNodeCount": len(validation.get("rejectedNodes", [])),
        "ignoredNodeCount": len(validation.get("ignoredNodes", [])),
        "fallbackBatchCount": len(fallback_batches),
        "acceptedLeafCount": len(accepted_leaf_ids),
        "totalEvidenceCount": len(total_evidence),
        "coverage": float(len(accepted_leaf_ids)) / float(len(total_evidence)) if total_evidence else 0,
        "duplicateLeafOwnershipCount": reason_counts.get("duplicate_leaf_owner", 0),
        "bboxDriftCount": 0,
        "ocrMismatchCount": 0,
        "cycleCount": reason_counts.get("cycle", 0),
        "zeroChildGroupCount": reason_counts.get("zero_child_group", 0),
        "oneChildGroupCount": reason_counts.get("one_child_group", 0),
        "overflowNodeCount": reason_counts.get("required_size_overflow", 0),
        "highGapNodeCount": reason_counts.get("actual_gap_too_large", 0) + reason_counts.get("gap_too_large", 0),
        "crossAxisRejectedCount": reason_counts.get("cross_axis_spread_high", 0),
        "gapVarianceRejectedCount": reason_counts.get("gap_variance_high", 0),
        "physicalRejectedNodeCount": physical,
        "providerErrorCount": len(provider_errors),
        "repairAttemptCount": len(repair_attempts),
        "errorCount": len(validation.get("rejectedNodes", [])) + len(fallback_batches),
    }


def validation_for_batch(validation: dict[str, Any], batch_id: str) -> dict[str, Any] | None:
    for item in validation.get("batches", []):
        if item.get("batchId") == batch_id:
            return item
    return None


def rejection_summary(rejections: list[dict[str, Any]]) -> str:
    if not rejections:
        return ""
    counts = Counter(str(item.get("reason", "")).split(":", 1)[0] for item in rejections)
    return ",".join(f"{key}:{value}" for key, value in sorted(counts.items()))


def should_repair_batch(validation: dict[str, Any], batch_id: str) -> bool:
    reasons = [
        str(item.get("reason", "")).split(":", 1)[0]
        for item in validation.get("rejectedNodes", [])
        if item.get("batchId") == batch_id
    ]
    if not reasons:
        return False
    repairable = {
        "bad_result_version",
        "nodes_not_array",
        "node_not_object",
        "empty_group_id",
        "duplicate_group_id",
        "unknown_child_ref",
        "unknown_root_ref",
        "children_not_array",
        "zero_child_group",
        "one_child_group",
        "self_reference",
        "cycle",
        "multi_parent_group",
        "duplicate_leaf_owner",
        "invalid_child_group",
        "parse_or_provider_error",
    }
    return any(reason in repairable for reason in reasons)


def tree_prompt(input_doc: dict[str, Any], batch: dict[str, Any], previous_raw: str = "", previous_validation: dict[str, Any] | None = None) -> str:
    compact_batch = compact_batch_input(input_doc, batch)
    lines = [
        "You are a UI layout tree advisor for a PNG-to-editable-Figma pipeline.",
        "Return ONLY strict JSON. Do not return markdown, HTML, CSS, SVG, or Figma code.",
        f"Your output version must be {RESULT_VERSION}.",
        "You may reference ONLY evidence IDs from the current batch and group IDs that you define in nodes.",
        "Do not invent or modify text, bboxes, coordinates, assets, colors, or page content.",
        "The screenshot image is a crop for this batch. Evidence has both global bbox and crop-local bbox.",
        "Build a nested tree: small rows first, then parent cards/lists/toolbars when visually clear.",
        "Use horizontal for row-like groups and vertical for stacked groups.",
        "Every group must have at least two children and confidence between 0 and 1.",
        "Use confidence >= 0.70 only for groups you believe are physically valid. Omit uncertain groups instead of returning low confidence.",
        "A group child may reference another group. A leaf evidence ID should appear under one direct group only.",
        "Parent groups should usually contain child groups, not many far-apart leaf evidence IDs.",
        "For a horizontal group, children must share the same visual row and typical adjacent gap should be <= 96px.",
        "For a vertical group, children must form a clear stack; do not group columns or unrelated card fragments.",
        "If a parent would require a huge gap, split it or omit the parent.",
        "roots must list only top-level groups with no parent. If no safe groups exist, return roots: [] and nodes: [].",
        "Do not force coverage. Put uncertain evidence in ungrouped.",
        "Do not output bboxes; the deterministic validator computes bboxes from children.",
        "Expected JSON shape:",
        json.dumps(
            {
                "version": RESULT_VERSION,
                "nodes": [
                    {
                        "id": "group_001",
                        "name": "short_name",
                        "direction": "horizontal",
                        "children": ["evidence_id_1", "group_002"],
                        "gap": 12,
                        "confidence": 0.82,
                        "reason": "short reason",
                    }
                ],
                "roots": ["group_001"],
                "ungrouped": ["evidence_id_9"],
                "warnings": [],
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        "Current batch JSON:",
        json.dumps(compact_batch, ensure_ascii=False, separators=(",", ":")),
    ]
    if previous_raw or previous_validation:
        lines.extend(
            [
                "Repair the previous response. Keep the same contract and fix only the rejected structure.",
                "Previous raw response:",
                previous_raw[:8000],
                "Validation rejection summary:",
                json.dumps(compact_validation(previous_validation or {}), ensure_ascii=False, separators=(",", ":"))[:8000],
            ]
        )
    return "\n".join(lines)


def compact_batch_input(input_doc: dict[str, Any], batch: dict[str, Any]) -> dict[str, Any]:
    return {
        "sourceImage": input_doc.get("sourceImage"),
        "batchId": batch.get("id"),
        "sectionId": batch.get("sectionId"),
        "sectionBBox": batch.get("sectionBBox"),
        "cropBBox": batch.get("cropBBox"),
        "complexity": batch.get("complexity"),
        "evidence": [
            {
                "id": item.get("id"),
                "role": item.get("roleHint") or item.get("kind"),
                "bbox": item.get("bbox"),
                "bboxLocal": item.get("bboxLocal"),
                **({"text": item.get("text")} if str(item.get("text") or "").strip() else {}),
            }
            for item in batch.get("evidence", [])
        ],
    }


def compact_validation(validation: dict[str, Any]) -> dict[str, Any]:
    rejected_nodes = validation.get("rejectedNodes", [])
    return {
        "summary": validation.get("summary", {}),
        "rejectedNodes": [
            {
                "batchId": item.get("batchId"),
                "groupId": item.get("groupId"),
                "reason": item.get("reason"),
            }
            for item in rejected_nodes[:40]
        ],
    }


def call_provider(prompt: str, image_data_url: str, options: Options) -> str:
    base_url = env_first(("UNIFIED_VISION_BASE_URL", "LAYOUT_ADVISOR_BASE_URL", "CODIA_UI_DETECTOR_BASE_URL"), "https://api.openai.com").rstrip("/")
    api_key = env_first(("UNIFIED_VISION_API_KEY", "LAYOUT_ADVISOR_API_KEY", "CODIA_UI_DETECTOR_API_KEY"), "")
    model = env_first(("UNIFIED_VISION_MODEL", "LAYOUT_ADVISOR_MODEL", "CODIA_UI_DETECTOR_MODEL"), "")
    wire_api = env_first(("UNIFIED_VISION_WIRE_API", "LAYOUT_ADVISOR_WIRE_API", "CODIA_UI_DETECTOR_WIRE_API"), "responses").strip().lower()
    if not api_key:
        raise RuntimeError("missing UNIFIED_VISION_API_KEY or fallback provider API key")
    if not model:
        raise RuntimeError("missing UNIFIED_VISION_MODEL or fallback provider model")
    if wire_api in ("responses", "response"):
        payload: dict[str, Any] = {
            "model": model,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                        {"type": "input_image", "image_url": image_data_url},
                    ],
                }
            ],
        }
        if options.temperature > 0:
            payload["temperature"] = options.temperature
        response = post_json(request_url(base_url, "/responses"), payload, api_key, options)
        return extract_responses_text(response)
    if wire_api in ("chat.completions", "chat-completions", "chat"):
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_data_url}},
                    ],
                }
            ],
        }
        if options.temperature > 0:
            payload["temperature"] = options.temperature
        response = post_json(request_url(base_url, "/chat/completions"), payload, api_key, options)
        return response["choices"][0]["message"]["content"]
    raise RuntimeError(f"unsupported UNIFIED_VISION_WIRE_API {wire_api!r}")


def post_json(url: str, payload: dict[str, Any], api_key: str, options: Options) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    for attempt in range(max(1, options.transport_retries)):
        request = urllib.request.Request(url, data=data, headers=provider_headers(api_key), method="POST")
        try:
            with urllib.request.urlopen(request, timeout=options.timeout_seconds) as response:  # noqa: S310 - user-configured provider.
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            if exc.code in TRANSIENT_PROVIDER_STATUS and attempt < options.transport_retries - 1:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise RuntimeError(f"provider HTTP {exc.code}: {body[:500]}") from exc
        except (urllib.error.URLError, TimeoutError, http.client.RemoteDisconnected) as exc:
            if attempt < options.transport_retries - 1:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise RuntimeError(f"provider connection error: {exc}") from exc
    raise RuntimeError("provider request failed after retries")


def provider_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "curl/8.7.1",
    }


def request_url(base_url: str, api_path: str) -> str:
    base = str(base_url or "").strip().rstrip("/")
    path = "/" + str(api_path or "").strip().lstrip("/")
    if base.endswith("/v1"):
        return base + path
    if base.endswith(path) or "/v1/" in base:
        return base
    return base + "/v1" + path


def extract_responses_text(response: dict[str, Any]) -> str:
    texts: list[str] = []
    for item in response.get("output", []):
        for content in item.get("content", []):
            if content.get("type") in ("output_text", "text") and content.get("text"):
                texts.append(str(content["text"]))
    if not texts and response.get("output_text"):
        texts.append(str(response["output_text"]))
    if not texts:
        raise RuntimeError("provider response did not contain output text")
    return "\n".join(texts)


def parse_result_text(text: str) -> dict[str, Any]:
    raw = str(text or "").strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        raw = "\n".join(lines).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start < 0 or end <= start:
            raise
        return json.loads(raw[start : end + 1])


def crop_data_url(image_path: Path, crop_box: dict[str, int]) -> str:
    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - environment issue.
        raise RuntimeError("Pillow is required for provider mode") from exc
    with Image.open(image_path) as image:
        x1 = max(0, crop_box["x"])
        y1 = max(0, crop_box["y"])
        x2 = min(image.width, crop_box["x"] + crop_box["width"])
        y2 = min(image.height, crop_box["y"] + crop_box["height"])
        if x2 <= x1 or y2 <= y1:
            raise RuntimeError(f"empty crop bbox {crop_box}")
        cropped = image.crop((x1, y1, x2, y2))
        buf = io.BytesIO()
        cropped.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def rect(value: Any) -> dict[str, int]:
    value = value or {}
    return {
        "x": int(round(float(value.get("x", 0) or 0))),
        "y": int(round(float(value.get("y", 0) or 0))),
        "width": int(round(float(value.get("width", 0) or 0))),
        "height": int(round(float(value.get("height", 0) or 0))),
    }


def rect_right(value: dict[str, int]) -> int:
    return value["x"] + value["width"]


def rect_bottom(value: dict[str, int]) -> int:
    return value["y"] + value["height"]


def rect_empty(value: dict[str, int]) -> bool:
    return value["width"] <= 0 or value["height"] <= 0


def union_rects(values: list[dict[str, int]]) -> dict[str, int]:
    clean = [value for value in values if not rect_empty(value)]
    if not clean:
        return {"x": 0, "y": 0, "width": 0, "height": 0}
    x1 = min(value["x"] for value in clean)
    y1 = min(value["y"] for value in clean)
    x2 = max(rect_right(value) for value in clean)
    y2 = max(rect_bottom(value) for value in clean)
    return {"x": x1, "y": y1, "width": x2 - x1, "height": y2 - y1}


def median(values: list[int]) -> int:
    clean = sorted(value for value in values if value > 0)
    if not clean:
        return 0
    mid = len(clean) // 2
    if len(clean) % 2:
        return clean[mid]
    return int(round((clean[mid - 1] + clean[mid]) / 2))


def variance(values: list[int]) -> int:
    if len(values) <= 1:
        return 0
    mean = sum(values) / len(values)
    return int(round(sum((value - mean) ** 2 for value in values) / len(values)))


def as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def as_int(value: Any, default: int) -> int:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return default


def unique(values: list[str]) -> list[str]:
    seen = set()
    out = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in value) or "batch"


def write_json(path: Path, value: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def write_text(path: Path, value: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")
    return path


def env_first(keys: tuple[str, ...], default: str) -> str:
    for key in keys:
        value = os.environ.get(key)
        if value is not None and value != "":
            return value
    return default


def timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


if __name__ == "__main__":
    sys.exit(main())
