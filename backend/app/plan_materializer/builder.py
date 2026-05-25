from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from ..dsl_factory import build_deterministic_dsl
from ..m29_materialization_utils import list_dicts
from ..png_tools import UnsupportedPngCropError, decode_png_pixels, read_png_metadata
from ..text_masked_media_audit import text_boxes_from_ocr_document
from .assets import relative_posix, resolve_m29_dir
from .background import apply_source_background
from .cleanup import clean_internal_assets_from_copied_image_assets, clean_text_from_copied_image_assets, erase_replayed_bboxes_from_fallback
from .replay import replay_m295_plan_items
from .report import build_summary
from .structure import materialize_controlled_structure_groups
from .types import PlanMaterializerOptions, PlanMaterializerResult, ReplayNode


def build_plan_driven_dsl(
    *,
    source_png: bytes,
    source_image_path: str,
    m29_document: dict[str, Any],
    output_dir: Path,
    ocr_document: dict[str, Any] | None = None,
    m292_document: dict[str, Any] | None = None,
    m295_replay_plan: dict[str, Any] | None = None,
    hierarchy_report: dict[str, Any] | None = None,
    sibling_group_report: dict[str, Any] | None = None,
    layout_energy_report: dict[str, Any] | None = None,
    auto_layout_permission_report: dict[str, Any] | None = None,
    extra_warnings: list[str] | None = None,
    options: PlanMaterializerOptions | None = None,
    task_id: str = "materialized_design",
) -> PlanMaterializerResult:
    options = options or PlanMaterializerOptions()
    image = read_png_metadata(source_png)
    if image is None:
        raise UnsupportedPngCropError("M29 plan-driven replay source image is not a readable PNG.")
    pixels = decode_png_pixels(source_png)
    output_dir.mkdir(parents=True, exist_ok=True)

    source_path = Path(source_image_path).expanduser()
    fallback_dir = output_dir / "assets" / "m29_fallback"
    fallback_dir.mkdir(parents=True, exist_ok=True)
    fallback_path = fallback_dir / (source_path.name or "source.png")
    fallback_path.write_bytes(source_png)

    dsl = build_deterministic_dsl(
        task_id=task_id,
        original_url=str(source_path),
        fallback_url=relative_posix(output_dir, fallback_path),
        image=image,
        quality_flags=["m29_plan_driven_materialization"],
    )
    apply_source_background(dsl, pixels)
    namespace_base_dsl(dsl)
    dsl["meta"].update(
        {
            "notes": "m29_plan_driven_materialization",
            "m29PlanDrivenMaterialization": True,
            "sourceM29MainlineMaterialization": "mainline",
        }
    )

    existing_ids = collect_element_ids(dsl["root"])
    asset_ids = {str(asset.get("assetId")) for asset in list_dicts(dsl.get("assets")) if asset.get("assetId")}
    replayed: list[ReplayNode] = []
    skipped: list[dict[str, Any]] = []
    warnings: list[str] = []

    ocr_boxes = []
    if extra_warnings:
        warnings.extend(extra_warnings)
    if ocr_document is not None:
        ocr_boxes, ocr_warnings = text_boxes_from_ocr_document(ocr_document)
        warnings.extend(ocr_warnings)
    elif options.enable_text_replay:
        warnings.append("ocr_missing_text_replay_disabled")

    m29_nodes = list_dicts(m29_document.get("nodes"))
    m292_objects = list_dicts((m292_document or {}).get("sourceObjects"))
    if m295_replay_plan is None:
        raise ValueError("M29.5 replay plan is required for plan-driven materialization.")
    m295_plan_items = list_dicts(m295_replay_plan.get("planItems"))
    replay_m295_plan_items(
        dsl=dsl,
        existing_ids=existing_ids,
        asset_ids=asset_ids,
        pixels=pixels,
        image=image,
        m29_nodes=m29_nodes,
        m29_dir=resolve_m29_dir(m29_document),
        output_dir=output_dir,
        ocr_boxes=ocr_boxes,
        m292_objects=m292_objects,
        plan_items=m295_plan_items,
        replayed=replayed,
        skipped=skipped,
        options=options,
    )

    copied_image_asset_text_erased_count = clean_text_from_copied_image_assets(
        dsl,
        output_dir,
        replayed,
        plan_items=m295_plan_items,
    )
    copied_image_asset_internal_erased_count = clean_internal_assets_from_copied_image_assets(
        dsl,
        output_dir,
        replayed,
        plan_items=m295_plan_items,
    )

    fallback_erased_count = 0
    if options.erase_replayed_bboxes_from_fallback:
        fallback_erased_count = erase_replayed_bboxes_from_fallback(dsl, output_dir, pixels, replayed, plan_items=m295_plan_items)

    structure_report = materialize_controlled_structure_groups(
        dsl=dsl,
        replayed=replayed,
        existing_ids=existing_ids,
        hierarchy_report=hierarchy_report,
        sibling_group_report=sibling_group_report,
        layout_energy_report=layout_energy_report,
        auto_layout_permission_report=auto_layout_permission_report,
        options=options,
    )

    summary = build_summary(
        m29_document=m29_document,
        ocr_count=len(ocr_boxes),
        replayed=replayed,
        skipped=skipped,
        fallback_erased_count=fallback_erased_count,
        copied_image_asset_text_erased_count=copied_image_asset_text_erased_count,
        copied_image_asset_internal_erased_count=copied_image_asset_internal_erased_count,
        options=options,
        structure_report=structure_report,
    )
    if isinstance((m292_document or {}).get("summary"), dict):
        summary["m292SourcePhysicalGraph"] = dict(m292_document["summary"])
    if isinstance((m295_replay_plan or {}).get("summary"), dict):
        summary["m295ReplayPlan"] = dict(m295_replay_plan["summary"])
    report = {
        "schemaName": "M29PlanMaterializationReport",
        "schemaVersion": "0.1",
        "sourceImage": source_image_path,
        "summary": summary,
        "options": options.to_dict(),
        "controlledStructureMaterialization": structure_report,
        "replayedNodes": [asdict(item) for item in replayed],
        "skippedItems": skipped,
        "warnings": warnings,
        "meta": {
            "dslChanged": True,
            "branchOnlyExperiment": False,
            "truthSource": "source_png_plus_ocr_plus_m29_5_replay_plan",
        },
    }
    (output_dir / "design.dsl.json").write_text(json.dumps(dsl, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "materialization_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return PlanMaterializerResult(dsl=dsl, report=report)


def namespace_base_dsl(dsl: dict[str, Any]) -> None:
    asset_id_map = {
        "asset_original": "m29_asset_original",
        "asset_banner": "m29_asset_fallback",
    }
    for asset in list_dicts(dsl.get("assets")):
        asset_id = str(asset.get("assetId") or "")
        if asset_id in asset_id_map:
            asset["assetId"] = asset_id_map[asset_id]

    root = dsl.get("root")
    if not isinstance(root, dict):
        return
    root["id"] = "m29_root"
    root["name"] = "M29 Plan Materialized Design"
    rewrite_element_asset_refs(root, asset_id_map)


def rewrite_element_asset_refs(element: dict[str, Any], asset_id_map: dict[str, str]) -> None:
    element_id = str(element.get("id") or "")
    if element_id == "original_ref":
        element["id"] = "m29_original_ref"
    elif element_id == "fallback_full_image":
        element["id"] = "m29_fallback_full_image"

    source = element.get("source")
    if isinstance(source, dict):
        asset_id = str(source.get("assetId") or "")
        if asset_id in asset_id_map:
            source["assetId"] = asset_id_map[asset_id]

    for child in list_dicts(element.get("children")):
        rewrite_element_asset_refs(child, asset_id_map)


def collect_element_ids(root: dict[str, Any]) -> set[str]:
    ids: set[str] = set()

    def visit(node: dict[str, Any]) -> None:
        if isinstance(node.get("id"), str):
            ids.add(node["id"])
        for child in node.get("children", []) if isinstance(node.get("children"), list) else []:
            if isinstance(child, dict):
                visit(child)

    visit(root)
    return ids
