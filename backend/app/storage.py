from __future__ import annotations

import shutil
from pathlib import Path


class Storage:
    def __init__(self, root: Path, public_base_url: str) -> None:
        self.root = root
        self.public_base_url = public_base_url.rstrip("/")
        self.uploads_dir = root / "uploads"
        self.assets_dir = root / "assets"
        self.dsl_dir = root / "dsl"
        self.primitives_dir = root / "primitives"
        self.ocr_dir = root / "ocr"
        self.patches_dir = root / "patches"
        self.text_replacements_dir = root / "text_replacements"
        self.text_bindings_dir = root / "text_bindings"
        self.component_structures_dir = root / "component_structures"
        self.component_annotations_dir = root / "component_annotations"
        self.layer_separation_candidates_dir = root / "layer_separation_candidates"
        self.asset_slice_candidates_dir = root / "asset_slice_candidates"
        self.icon_candidates_dir = root / "icon_candidates"
        self.icon_coverage_audits_dir = root / "icon_coverage_audits"
        self.icon_gap_candidates_dir = root / "icon_gap_candidates"
        self.icon_placement_plans_dir = root / "icon_placement_plans"
        self.icon_visible_fallbacks_dir = root / "icon_visible_fallbacks"
        self.icon_business_candidates_dir = root / "icon_business_candidates"
        self.perception_benchmarks_dir = root / "perception_benchmarks"
        self.sam_visual_candidates_dir = root / "sam_visual_candidates"
        self.logs_dir = root / "logs"
        self.ensure_dirs()

    def ensure_dirs(self) -> None:
        for directory in [
            self.uploads_dir,
            self.assets_dir,
            self.dsl_dir,
            self.primitives_dir,
            self.ocr_dir,
            self.patches_dir,
            self.text_replacements_dir,
            self.text_bindings_dir,
            self.component_structures_dir,
            self.component_annotations_dir,
            self.layer_separation_candidates_dir,
            self.asset_slice_candidates_dir,
            self.icon_candidates_dir,
            self.icon_coverage_audits_dir,
            self.icon_gap_candidates_dir,
            self.icon_placement_plans_dir,
            self.icon_visible_fallbacks_dir,
            self.icon_business_candidates_dir,
            self.perception_benchmarks_dir,
            self.sam_visual_candidates_dir,
            self.logs_dir,
        ]:
            directory.mkdir(parents=True, exist_ok=True)

    def upload_path(self, task_id: str) -> Path:
        return self.uploads_dir / task_id / "original.png"

    def banner_path(self, task_id: str) -> Path:
        return self.assets_dir / task_id / "banner.png"

    def region_path(self, task_id: str, region_name: str) -> Path:
        return self.assets_dir / task_id / f"{region_name}.png"

    def dsl_path(self, task_id: str) -> Path:
        return self.dsl_dir / f"{task_id}.json"

    def base_dsl_path(self, task_id: str) -> Path:
        return self.dsl_dir / f"{task_id}.base.json"

    def primitive_path(self, task_id: str) -> Path:
        return self.primitives_dir / f"{task_id}.json"

    def ocr_path(self, task_id: str) -> Path:
        return self.ocr_dir / f"{task_id}.json"

    def patch_path(self, task_id: str) -> Path:
        return self.patches_dir / f"{task_id}.json"

    def text_replacement_path(self, task_id: str) -> Path:
        return self.text_replacements_dir / f"{task_id}.json"

    def text_binding_path(self, task_id: str) -> Path:
        return self.text_bindings_dir / f"{task_id}.json"

    def component_structure_path(self, task_id: str) -> Path:
        return self.component_structures_dir / f"{task_id}.json"

    def component_annotation_path(self, task_id: str) -> Path:
        return self.component_annotations_dir / f"{task_id}.json"

    def layer_separation_path(self, task_id: str) -> Path:
        return self.layer_separation_candidates_dir / f"{task_id}.json"

    def asset_slice_path(self, task_id: str) -> Path:
        return self.asset_slice_candidates_dir / f"{task_id}.json"

    def icon_candidate_path(self, task_id: str) -> Path:
        return self.icon_candidates_dir / f"{task_id}.json"

    def icon_coverage_audit_path(self, task_id: str) -> Path:
        return self.icon_coverage_audits_dir / f"{task_id}.json"

    def icon_gap_candidate_path(self, task_id: str) -> Path:
        return self.icon_gap_candidates_dir / f"{task_id}.json"

    def icon_placement_plan_path(self, task_id: str) -> Path:
        return self.icon_placement_plans_dir / f"{task_id}.json"

    def icon_visible_fallback_path(self, task_id: str) -> Path:
        return self.icon_visible_fallbacks_dir / f"{task_id}.json"

    def icon_business_candidate_path(self, task_id: str) -> Path:
        return self.icon_business_candidates_dir / f"{task_id}.json"

    def perception_benchmark_path(self, task_id: str) -> Path:
        return self.perception_benchmarks_dir / f"{task_id}.json"

    def sam_visual_candidate_path(self, task_id: str) -> Path:
        return self.sam_visual_candidates_dir / f"{task_id}.json"

    def asset_slice_image_path(self, task_id: str, filename: str) -> Path:
        return self.assets_dir / task_id / "slices" / filename

    def icon_candidate_image_path(self, task_id: str, filename: str) -> Path:
        return self.assets_dir / task_id / "icons" / filename

    def icon_gap_candidate_image_path(self, task_id: str, filename: str) -> Path:
        return self.assets_dir / task_id / "icons_gap" / filename

    def icon_business_candidate_image_path(self, task_id: str, filename: str) -> Path:
        return self.assets_dir / task_id / "icons_business" / filename

    def m30_asset_path(self, task_id: str, filename: str) -> Path:
        return self.assets_dir / task_id / "m30" / filename

    def original_url(self, task_id: str) -> str:
        return f"{self.public_base_url}/files/uploads/{task_id}/original.png"

    def banner_url(self, task_id: str) -> str:
        return f"{self.public_base_url}/files/assets/{task_id}/banner.png"

    def region_url(self, task_id: str, region_name: str) -> str:
        return f"{self.public_base_url}/files/assets/{task_id}/{region_name}.png"

    def asset_slice_image_url(self, task_id: str, filename: str) -> str:
        return f"{self.public_base_url}/files/assets/{task_id}/slices/{filename}"

    def icon_candidate_image_url(self, task_id: str, filename: str) -> str:
        return f"{self.public_base_url}/files/assets/{task_id}/icons/{filename}"

    def icon_gap_candidate_image_url(self, task_id: str, filename: str) -> str:
        return f"{self.public_base_url}/files/assets/{task_id}/icons_gap/{filename}"

    def icon_business_candidate_image_url(self, task_id: str, filename: str) -> str:
        return f"{self.public_base_url}/files/assets/{task_id}/icons_business/{filename}"

    def m30_asset_url(self, task_id: str, filename: str) -> str:
        return f"{self.public_base_url}/files/assets/{task_id}/m30/{filename}"

    def save_upload(self, task_id: str, data: bytes) -> Path:
        path = self.upload_path(task_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def create_banner_asset(self, task_id: str, upload_path: Path) -> Path:
        path = self.banner_path(task_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(upload_path, path)
        return path

    def save_region_asset(self, task_id: str, region_name: str, data: bytes) -> Path:
        path = self.region_path(task_id, region_name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def save_primitives(self, task_id: str, data: str) -> Path:
        path = self.primitive_path(task_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data, encoding="utf-8")
        return path

    def save_ocr(self, task_id: str, data: str) -> Path:
        path = self.ocr_path(task_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data, encoding="utf-8")
        return path

    def save_patch(self, task_id: str, data: str) -> Path:
        path = self.patch_path(task_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data, encoding="utf-8")
        return path

    def save_text_replacement(self, task_id: str, data: str) -> Path:
        path = self.text_replacement_path(task_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data, encoding="utf-8")
        return path

    def save_text_binding(self, task_id: str, data: str) -> Path:
        path = self.text_binding_path(task_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data, encoding="utf-8")
        return path

    def save_component_structure(self, task_id: str, data: str) -> Path:
        path = self.component_structure_path(task_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data, encoding="utf-8")
        return path

    def save_component_annotation(self, task_id: str, data: str) -> Path:
        path = self.component_annotation_path(task_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data, encoding="utf-8")
        return path

    def save_layer_separation(self, task_id: str, data: str) -> Path:
        path = self.layer_separation_path(task_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data, encoding="utf-8")
        return path

    def save_asset_slice(self, task_id: str, data: str) -> Path:
        path = self.asset_slice_path(task_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data, encoding="utf-8")
        return path

    def save_icon_candidate(self, task_id: str, data: str) -> Path:
        path = self.icon_candidate_path(task_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data, encoding="utf-8")
        return path

    def save_icon_coverage_audit(self, task_id: str, data: str) -> Path:
        path = self.icon_coverage_audit_path(task_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data, encoding="utf-8")
        return path

    def save_icon_gap_candidate(self, task_id: str, data: str) -> Path:
        path = self.icon_gap_candidate_path(task_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data, encoding="utf-8")
        return path

    def save_icon_placement_plan(self, task_id: str, data: str) -> Path:
        path = self.icon_placement_plan_path(task_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data, encoding="utf-8")
        return path

    def save_icon_visible_fallback(self, task_id: str, data: str) -> Path:
        path = self.icon_visible_fallback_path(task_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data, encoding="utf-8")
        return path

    def save_icon_business_candidate(self, task_id: str, data: str) -> Path:
        path = self.icon_business_candidate_path(task_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data, encoding="utf-8")
        return path

    def save_perception_benchmark(self, task_id: str, data: str) -> Path:
        path = self.perception_benchmark_path(task_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data, encoding="utf-8")
        return path

    def save_sam_visual_candidate(self, task_id: str, data: str) -> Path:
        path = self.sam_visual_candidate_path(task_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data, encoding="utf-8")
        return path

    def save_asset_slice_image(self, task_id: str, filename: str, data: bytes) -> Path:
        path = self.asset_slice_image_path(task_id, filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def save_icon_candidate_image(self, task_id: str, filename: str, data: bytes) -> Path:
        path = self.icon_candidate_image_path(task_id, filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def save_icon_gap_candidate_image(self, task_id: str, filename: str, data: bytes) -> Path:
        path = self.icon_gap_candidate_image_path(task_id, filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path
