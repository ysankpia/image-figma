from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


_LOCAL_ENV_LOADED = False


@dataclass(frozen=True)
class Settings:
    version: str
    storage_root: Path
    database_path: Path
    public_base_url: str
    max_upload_bytes: int
    cors_allow_origins: list[str]
    visual_primitive_provider: str
    ocr_provider: str
    dsl_patch_mode: str
    openai_api_key: str | None
    openai_vision_model: str
    openai_timeout_seconds: float
    ocr_min_confidence: float = 0.70
    baidu_paddle_ocr_token: str | None = None
    baidu_paddle_ocr_job_url: str = "https://paddleocr.aistudio-app.com/api/v2/ocr/jobs"
    baidu_paddle_ocr_model: str = "PP-OCRv5"
    baidu_paddle_ocr_poll_interval_seconds: float = 5
    baidu_paddle_ocr_timeout_seconds: float = 120
    text_replacement_mode: str = "debug"
    text_replacement_max_blocks: int = 100
    text_replacement_min_confidence: float = 0.95
    text_replacement_solid_bg_tolerance: int = 18
    text_replacement_max_height: int = 64
    text_replacement_min_width: int = 12
    text_replacement_min_height: int = 10
    text_replacement_enable_colored_bg: bool = True
    text_replacement_min_contrast: int = 90
    text_replacement_edge_sample_padding: int = 4
    text_replacement_text_sample_inset: int = 1
    text_replacement_ui_aware_sampling: bool = True
    text_replacement_local_bg_tolerance: int = 24
    text_replacement_max_rescue_strategies: int = 4
    text_binding_enabled: bool = True
    text_binding_min_confidence: float = 0.70
    component_structure_enabled: bool = True
    component_structure_min_confidence: float = 0.70
    component_annotation_enabled: bool = True
    component_annotation_layer_naming: bool = True
    component_annotation_min_confidence: float = 0.70
    layer_separation_enabled: bool = True
    layer_separation_min_confidence: float = 0.70
    layer_separation_simple_fill_tolerance: int = 24
    layer_separation_max_component_area_ratio: float = 0.35
    asset_slice_enabled: bool = True
    asset_slice_max_candidates: int = 24
    asset_slice_min_confidence: float = 0.70
    asset_slice_max_area_ratio: float = 0.25
    asset_slice_generate_filled: bool = True
    icon_candidate_enabled: bool = True
    icon_candidate_min_confidence: float = 0.70
    icon_candidate_max_candidates: int = 64
    icon_candidate_min_size: int = 8
    icon_candidate_max_size: int = 96
    icon_candidate_foreground_distance: int = 32
    icon_candidate_max_component_area_ratio: float = 0.20
    icon_coverage_audit_enabled: bool = True
    icon_coverage_overlay_enabled: bool = True
    icon_coverage_missed_hints_enabled: bool = True
    icon_coverage_min_hint_confidence: float = 0.60
    icon_coverage_max_missed_hints: int = 80
    icon_coverage_foreground_distance: int = 32
    icon_gap_candidate_enabled: bool = True
    icon_gap_candidate_min_confidence: float = 0.72
    icon_gap_candidate_max_candidates: int = 48
    icon_gap_candidate_min_size: int = 8
    icon_gap_candidate_max_size: int = 80
    icon_gap_candidate_foreground_distance: int = 32
    icon_gap_candidate_retry_padding: int = 12
    icon_gap_candidate_edge_clip_tolerance: int = 3
    icon_gap_candidate_overlay_enabled: bool = True
    icon_placement_plan_enabled: bool = True
    icon_placement_plan_overlay_enabled: bool = True
    icon_placement_plan_dedup_iou: float = 0.50
    icon_placement_plan_text_overlap_iou: float = 0.10
    icon_placement_plan_slice_overlap_iou: float = 0.50
    icon_placement_plan_max_placements: int = 128
    icon_visible_fallback_enabled: bool = False
    icon_visible_fallback_max_placements: int = 12
    icon_visible_fallback_min_confidence: float = 0.85
    icon_visible_fallback_mask_padding: int = 2
    icon_visible_fallback_max_mask_size: int = 96
    icon_visible_fallback_solid_bg_tolerance: int = 28
    icon_visible_fallback_allowed_roles: list[str] = field(
        default_factory=lambda: ["nav_icon", "header_nav_icon", "header_action_icon", "leading_icon"]
    )
    icon_visible_fallback_overlay_enabled: bool = True
    icon_business_candidate_enabled: bool = True
    icon_business_candidate_max_candidates: int = 80
    icon_business_candidate_min_confidence: float = 0.70
    icon_business_candidate_min_size: int = 8
    icon_business_candidate_max_size: int = 96
    icon_business_candidate_foreground_distance: int = 32
    icon_business_candidate_retry_padding: int = 12
    icon_business_candidate_edge_clip_tolerance: int = 3
    icon_business_candidate_overlay_enabled: bool = True
    icon_business_bottom_nav_enabled: bool = True
    icon_business_primary_button_enabled: bool = True
    icon_business_shortcut_card_enabled: bool = True
    icon_business_metric_card_enabled: bool = True
    icon_business_room_card_enabled: bool = True
    icon_business_trailing_enabled: bool = True
    icon_business_tip_info_enabled: bool = True
    perception_benchmark_enabled: bool = False
    perception_benchmark_providers: list[str] = field(default_factory=lambda: ["current_rules", "opencv"])
    perception_benchmark_max_candidates_per_provider: int = 300
    perception_benchmark_overlay_enabled: bool = True
    perception_opencv_enabled: bool = False
    perception_opencv_import_name: str = "cv2"
    perception_sam2_enabled: bool = False
    perception_sam2_model_cfg: str = ""
    perception_sam2_checkpoint: str = ""
    perception_sam2_device: str = "auto"
    perception_sam2_max_image_edge: int = 1280
    perception_sam2_max_masks: int = 300
    perception_uied_enabled: bool = False
    perception_uied_command: str = ""
    m30_preview_profile: str = "production"
    legacy_pre_m29_upload_enabled: bool = False
    sam_visual_candidate_enabled: bool = False
    sam_visual_candidate_model_cfg: str = ""
    sam_visual_candidate_checkpoint: str = ""
    sam_visual_candidate_device: str = "auto"
    sam_visual_candidate_max_image_edge: int = 960
    sam_visual_candidate_max_masks: int = 300
    sam_visual_candidate_points_per_side: int = 8
    sam_visual_candidate_points_per_batch: int = 64
    sam_visual_candidate_max_candidates: int = 120
    sam_visual_candidate_min_confidence: float = 0.72
    sam_visual_candidate_min_area: int = 64
    sam_visual_candidate_max_area_ratio: float = 0.12
    sam_visual_candidate_text_overlap_iou: float = 0.10
    sam_visual_candidate_existing_icon_iou: float = 0.50
    sam_visual_candidate_overlay_enabled: bool = True


def get_settings() -> Settings:
    backend_root = Path(__file__).resolve().parents[1]
    load_local_env_file(backend_root.parent / ".env.local")
    storage_root = Path(os.getenv("STORAGE_ROOT", backend_root / "storage")).resolve()
    database_path = Path(os.getenv("DATABASE_PATH", storage_root / "app.db")).resolve()
    return Settings(
        version="0.1.0",
        storage_root=storage_root,
        database_path=database_path,
        public_base_url=os.getenv("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/"),
        max_upload_bytes=int(os.getenv("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024))),
        cors_allow_origins=parse_csv(os.getenv("CORS_ALLOW_ORIGINS", "*")),
        visual_primitive_provider=os.getenv("VISUAL_PRIMITIVE_PROVIDER", "fake").strip().lower() or "fake",
        ocr_provider=os.getenv("OCR_PROVIDER", "fake").strip().lower() or "fake",
        ocr_min_confidence=float(os.getenv("OCR_MIN_CONFIDENCE", "0.70")),
        dsl_patch_mode=os.getenv("DSL_PATCH_MODE", "debug").strip().lower() or "debug",
        baidu_paddle_ocr_token=os.getenv("BAIDU_PADDLE_OCR_TOKEN"),
        baidu_paddle_ocr_job_url=os.getenv(
            "BAIDU_PADDLE_OCR_JOB_URL",
            "https://paddleocr.aistudio-app.com/api/v2/ocr/jobs",
        ).rstrip("/"),
        baidu_paddle_ocr_model=os.getenv("BAIDU_PADDLE_OCR_MODEL", "PP-OCRv5").strip() or "PP-OCRv5",
        baidu_paddle_ocr_poll_interval_seconds=float(os.getenv("BAIDU_PADDLE_OCR_POLL_INTERVAL_SECONDS", "5")),
        baidu_paddle_ocr_timeout_seconds=float(os.getenv("BAIDU_PADDLE_OCR_TIMEOUT_SECONDS", "120")),
        text_replacement_mode=os.getenv("TEXT_REPLACEMENT_MODE", "debug").strip().lower() or "debug",
        text_replacement_max_blocks=int(os.getenv("TEXT_REPLACEMENT_MAX_BLOCKS", "100")),
        text_replacement_min_confidence=float(os.getenv("TEXT_REPLACEMENT_MIN_CONFIDENCE", "0.95")),
        text_replacement_solid_bg_tolerance=int(os.getenv("TEXT_REPLACEMENT_SOLID_BG_TOLERANCE", "18")),
        text_replacement_max_height=int(os.getenv("TEXT_REPLACEMENT_MAX_HEIGHT", "64")),
        text_replacement_min_width=int(os.getenv("TEXT_REPLACEMENT_MIN_WIDTH", "12")),
        text_replacement_min_height=int(os.getenv("TEXT_REPLACEMENT_MIN_HEIGHT", "10")),
        text_replacement_enable_colored_bg=parse_bool(os.getenv("TEXT_REPLACEMENT_ENABLE_COLORED_BG", "true")),
        text_replacement_min_contrast=int(os.getenv("TEXT_REPLACEMENT_MIN_CONTRAST", "90")),
        text_replacement_edge_sample_padding=int(os.getenv("TEXT_REPLACEMENT_EDGE_SAMPLE_PADDING", "4")),
        text_replacement_text_sample_inset=int(os.getenv("TEXT_REPLACEMENT_TEXT_SAMPLE_INSET", "1")),
        text_replacement_ui_aware_sampling=parse_bool(os.getenv("TEXT_REPLACEMENT_UI_AWARE_SAMPLING", "true")),
        text_replacement_local_bg_tolerance=int(os.getenv("TEXT_REPLACEMENT_LOCAL_BG_TOLERANCE", "24")),
        text_replacement_max_rescue_strategies=int(os.getenv("TEXT_REPLACEMENT_MAX_RESCUE_STRATEGIES", "4")),
        text_binding_enabled=parse_bool(os.getenv("TEXT_BINDING_ENABLED", "true")),
        text_binding_min_confidence=float(os.getenv("TEXT_BINDING_MIN_CONFIDENCE", "0.70")),
        component_structure_enabled=parse_bool(os.getenv("COMPONENT_STRUCTURE_ENABLED", "true")),
        component_structure_min_confidence=float(os.getenv("COMPONENT_STRUCTURE_MIN_CONFIDENCE", "0.70")),
        component_annotation_enabled=parse_bool(os.getenv("COMPONENT_ANNOTATION_ENABLED", "true")),
        component_annotation_layer_naming=parse_bool(os.getenv("COMPONENT_ANNOTATION_LAYER_NAMING", "true")),
        component_annotation_min_confidence=float(os.getenv("COMPONENT_ANNOTATION_MIN_CONFIDENCE", "0.70")),
        layer_separation_enabled=parse_bool(os.getenv("LAYER_SEPARATION_ENABLED", "true")),
        layer_separation_min_confidence=float(os.getenv("LAYER_SEPARATION_MIN_CONFIDENCE", "0.70")),
        layer_separation_simple_fill_tolerance=int(os.getenv("LAYER_SEPARATION_SIMPLE_FILL_TOLERANCE", "24")),
        layer_separation_max_component_area_ratio=float(os.getenv("LAYER_SEPARATION_MAX_COMPONENT_AREA_RATIO", "0.35")),
        asset_slice_enabled=parse_bool(os.getenv("ASSET_SLICE_ENABLED", "true")),
        asset_slice_max_candidates=int(os.getenv("ASSET_SLICE_MAX_CANDIDATES", "24")),
        asset_slice_min_confidence=float(os.getenv("ASSET_SLICE_MIN_CONFIDENCE", "0.70")),
        asset_slice_max_area_ratio=float(os.getenv("ASSET_SLICE_MAX_AREA_RATIO", "0.25")),
        asset_slice_generate_filled=parse_bool(os.getenv("ASSET_SLICE_GENERATE_FILLED", "true")),
        icon_candidate_enabled=parse_bool(os.getenv("ICON_CANDIDATE_ENABLED", "true")),
        icon_candidate_min_confidence=float(os.getenv("ICON_CANDIDATE_MIN_CONFIDENCE", "0.70")),
        icon_candidate_max_candidates=int(os.getenv("ICON_CANDIDATE_MAX_CANDIDATES", "64")),
        icon_candidate_min_size=int(os.getenv("ICON_CANDIDATE_MIN_SIZE", "8")),
        icon_candidate_max_size=int(os.getenv("ICON_CANDIDATE_MAX_SIZE", "96")),
        icon_candidate_foreground_distance=int(os.getenv("ICON_CANDIDATE_FOREGROUND_DISTANCE", "32")),
        icon_candidate_max_component_area_ratio=float(os.getenv("ICON_CANDIDATE_MAX_COMPONENT_AREA_RATIO", "0.20")),
        icon_coverage_audit_enabled=parse_bool(os.getenv("ICON_COVERAGE_AUDIT_ENABLED", "true")),
        icon_coverage_overlay_enabled=parse_bool(os.getenv("ICON_COVERAGE_OVERLAY_ENABLED", "true")),
        icon_coverage_missed_hints_enabled=parse_bool(os.getenv("ICON_COVERAGE_MISSED_HINTS_ENABLED", "true")),
        icon_coverage_min_hint_confidence=float(os.getenv("ICON_COVERAGE_MIN_HINT_CONFIDENCE", "0.60")),
        icon_coverage_max_missed_hints=int(os.getenv("ICON_COVERAGE_MAX_MISSED_HINTS", "80")),
        icon_coverage_foreground_distance=int(os.getenv("ICON_COVERAGE_FOREGROUND_DISTANCE", "32")),
        icon_gap_candidate_enabled=parse_bool(os.getenv("ICON_GAP_CANDIDATE_ENABLED", "true")),
        icon_gap_candidate_min_confidence=float(os.getenv("ICON_GAP_CANDIDATE_MIN_CONFIDENCE", "0.72")),
        icon_gap_candidate_max_candidates=int(os.getenv("ICON_GAP_CANDIDATE_MAX_CANDIDATES", "48")),
        icon_gap_candidate_min_size=int(os.getenv("ICON_GAP_CANDIDATE_MIN_SIZE", "8")),
        icon_gap_candidate_max_size=int(os.getenv("ICON_GAP_CANDIDATE_MAX_SIZE", "80")),
        icon_gap_candidate_foreground_distance=int(os.getenv("ICON_GAP_CANDIDATE_FOREGROUND_DISTANCE", "32")),
        icon_gap_candidate_retry_padding=int(os.getenv("ICON_GAP_CANDIDATE_RETRY_PADDING", "12")),
        icon_gap_candidate_edge_clip_tolerance=int(os.getenv("ICON_GAP_CANDIDATE_EDGE_CLIP_TOLERANCE", "3")),
        icon_gap_candidate_overlay_enabled=parse_bool(os.getenv("ICON_GAP_CANDIDATE_OVERLAY_ENABLED", "true")),
        icon_placement_plan_enabled=parse_bool(os.getenv("ICON_PLACEMENT_PLAN_ENABLED", "true")),
        icon_placement_plan_overlay_enabled=parse_bool(os.getenv("ICON_PLACEMENT_PLAN_OVERLAY_ENABLED", "true")),
        icon_placement_plan_dedup_iou=float(os.getenv("ICON_PLACEMENT_PLAN_DEDUP_IOU", "0.50")),
        icon_placement_plan_text_overlap_iou=float(os.getenv("ICON_PLACEMENT_PLAN_TEXT_OVERLAP_IOU", "0.10")),
        icon_placement_plan_slice_overlap_iou=float(os.getenv("ICON_PLACEMENT_PLAN_SLICE_OVERLAP_IOU", "0.50")),
        icon_placement_plan_max_placements=int(os.getenv("ICON_PLACEMENT_PLAN_MAX_PLACEMENTS", "128")),
        icon_visible_fallback_enabled=parse_bool(os.getenv("ICON_VISIBLE_FALLBACK_ENABLED", "false")),
        icon_visible_fallback_max_placements=int(os.getenv("ICON_VISIBLE_FALLBACK_MAX_PLACEMENTS", "12")),
        icon_visible_fallback_min_confidence=float(os.getenv("ICON_VISIBLE_FALLBACK_MIN_CONFIDENCE", "0.85")),
        icon_visible_fallback_mask_padding=int(os.getenv("ICON_VISIBLE_FALLBACK_MASK_PADDING", "2")),
        icon_visible_fallback_max_mask_size=int(os.getenv("ICON_VISIBLE_FALLBACK_MAX_MASK_SIZE", "96")),
        icon_visible_fallback_solid_bg_tolerance=int(os.getenv("ICON_VISIBLE_FALLBACK_SOLID_BG_TOLERANCE", "28")),
        icon_visible_fallback_allowed_roles=parse_csv(
            os.getenv(
                "ICON_VISIBLE_FALLBACK_ALLOWED_ROLES",
                "nav_icon,header_nav_icon,header_action_icon,leading_icon",
            )
        ),
        icon_visible_fallback_overlay_enabled=parse_bool(os.getenv("ICON_VISIBLE_FALLBACK_OVERLAY_ENABLED", "true")),
        icon_business_candidate_enabled=parse_bool(os.getenv("ICON_BUSINESS_CANDIDATE_ENABLED", "true")),
        icon_business_candidate_max_candidates=int(os.getenv("ICON_BUSINESS_CANDIDATE_MAX_CANDIDATES", "80")),
        icon_business_candidate_min_confidence=float(os.getenv("ICON_BUSINESS_CANDIDATE_MIN_CONFIDENCE", "0.70")),
        icon_business_candidate_min_size=int(os.getenv("ICON_BUSINESS_CANDIDATE_MIN_SIZE", "8")),
        icon_business_candidate_max_size=int(os.getenv("ICON_BUSINESS_CANDIDATE_MAX_SIZE", "96")),
        icon_business_candidate_foreground_distance=int(os.getenv("ICON_BUSINESS_CANDIDATE_FOREGROUND_DISTANCE", "32")),
        icon_business_candidate_retry_padding=int(os.getenv("ICON_BUSINESS_CANDIDATE_RETRY_PADDING", "12")),
        icon_business_candidate_edge_clip_tolerance=int(os.getenv("ICON_BUSINESS_CANDIDATE_EDGE_CLIP_TOLERANCE", "3")),
        icon_business_candidate_overlay_enabled=parse_bool(os.getenv("ICON_BUSINESS_CANDIDATE_OVERLAY_ENABLED", "true")),
        icon_business_bottom_nav_enabled=parse_bool(os.getenv("ICON_BUSINESS_BOTTOM_NAV_ENABLED", "true")),
        icon_business_primary_button_enabled=parse_bool(os.getenv("ICON_BUSINESS_PRIMARY_BUTTON_ENABLED", "true")),
        icon_business_shortcut_card_enabled=parse_bool(os.getenv("ICON_BUSINESS_SHORTCUT_CARD_ENABLED", "true")),
        icon_business_metric_card_enabled=parse_bool(os.getenv("ICON_BUSINESS_METRIC_CARD_ENABLED", "true")),
        icon_business_room_card_enabled=parse_bool(os.getenv("ICON_BUSINESS_ROOM_CARD_ENABLED", "true")),
        icon_business_trailing_enabled=parse_bool(os.getenv("ICON_BUSINESS_TRAILING_ENABLED", "true")),
        icon_business_tip_info_enabled=parse_bool(os.getenv("ICON_BUSINESS_TIP_INFO_ENABLED", "true")),
        perception_benchmark_enabled=parse_bool(os.getenv("PERCEPTION_BENCHMARK_ENABLED", "false")),
        perception_benchmark_providers=parse_csv(os.getenv("PERCEPTION_BENCHMARK_PROVIDERS", "current_rules,opencv")),
        perception_benchmark_max_candidates_per_provider=int(os.getenv("PERCEPTION_BENCHMARK_MAX_CANDIDATES_PER_PROVIDER", "300")),
        perception_benchmark_overlay_enabled=parse_bool(os.getenv("PERCEPTION_BENCHMARK_OVERLAY_ENABLED", "true")),
        perception_opencv_enabled=parse_bool(os.getenv("PERCEPTION_OPENCV_ENABLED", "false")),
        perception_opencv_import_name=os.getenv("PERCEPTION_OPENCV_IMPORT_NAME", "cv2").strip() or "cv2",
        perception_sam2_enabled=parse_bool(os.getenv("PERCEPTION_SAM2_ENABLED", "false")),
        perception_sam2_model_cfg=os.getenv("PERCEPTION_SAM2_MODEL_CFG", "").strip(),
        perception_sam2_checkpoint=os.getenv("PERCEPTION_SAM2_CHECKPOINT", "").strip(),
        perception_sam2_device=os.getenv("PERCEPTION_SAM2_DEVICE", "auto").strip() or "auto",
        perception_sam2_max_image_edge=int(os.getenv("PERCEPTION_SAM2_MAX_IMAGE_EDGE", "1280")),
        perception_sam2_max_masks=int(os.getenv("PERCEPTION_SAM2_MAX_MASKS", "300")),
        perception_uied_enabled=parse_bool(os.getenv("PERCEPTION_UIED_ENABLED", "false")),
        perception_uied_command=os.getenv("PERCEPTION_UIED_COMMAND", "").strip(),
        m30_preview_profile=parse_m30_preview_profile(os.getenv("M30_PREVIEW_PROFILE", "production")),
        legacy_pre_m29_upload_enabled=parse_bool(os.getenv("LEGACY_PRE_M29_UPLOAD_ENABLED", "false")),
        sam_visual_candidate_enabled=parse_bool(os.getenv("SAM_VISUAL_CANDIDATE_ENABLED", "false")),
        sam_visual_candidate_model_cfg=os.getenv("SAM_VISUAL_CANDIDATE_MODEL_CFG", "").strip(),
        sam_visual_candidate_checkpoint=os.getenv("SAM_VISUAL_CANDIDATE_CHECKPOINT", "").strip(),
        sam_visual_candidate_device=os.getenv("SAM_VISUAL_CANDIDATE_DEVICE", "auto").strip() or "auto",
        sam_visual_candidate_max_image_edge=int(os.getenv("SAM_VISUAL_CANDIDATE_MAX_IMAGE_EDGE", "960")),
        sam_visual_candidate_max_masks=int(os.getenv("SAM_VISUAL_CANDIDATE_MAX_MASKS", "300")),
        sam_visual_candidate_points_per_side=int(os.getenv("SAM_VISUAL_CANDIDATE_POINTS_PER_SIDE", "8")),
        sam_visual_candidate_points_per_batch=int(os.getenv("SAM_VISUAL_CANDIDATE_POINTS_PER_BATCH", "64")),
        sam_visual_candidate_max_candidates=int(os.getenv("SAM_VISUAL_CANDIDATE_MAX_CANDIDATES", "120")),
        sam_visual_candidate_min_confidence=float(os.getenv("SAM_VISUAL_CANDIDATE_MIN_CONFIDENCE", "0.72")),
        sam_visual_candidate_min_area=int(os.getenv("SAM_VISUAL_CANDIDATE_MIN_AREA", "64")),
        sam_visual_candidate_max_area_ratio=float(os.getenv("SAM_VISUAL_CANDIDATE_MAX_AREA_RATIO", "0.12")),
        sam_visual_candidate_text_overlap_iou=float(os.getenv("SAM_VISUAL_CANDIDATE_TEXT_OVERLAP_IOU", "0.10")),
        sam_visual_candidate_existing_icon_iou=float(os.getenv("SAM_VISUAL_CANDIDATE_EXISTING_ICON_IOU", "0.50")),
        sam_visual_candidate_overlay_enabled=parse_bool(os.getenv("SAM_VISUAL_CANDIDATE_OVERLAY_ENABLED", "true")),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_vision_model=os.getenv("OPENAI_VISION_MODEL", "gpt-5.5").strip() or "gpt-5.5",
        openai_timeout_seconds=float(os.getenv("OPENAI_TIMEOUT_SECONDS", "30")),
    )


def load_local_env_file(path: Path) -> None:
    global _LOCAL_ENV_LOADED
    if _LOCAL_ENV_LOADED:
        return
    _LOCAL_ENV_LOADED = True
    if os.getenv("IMAGE_FIGMA_LOAD_LOCAL_ENV", "true").strip().lower() in {"0", "false", "no", "off"}:
        return
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        parsed = parse_env_line(raw_line)
        if parsed is None:
            continue
        key, value = parsed
        os.environ.setdefault(key, value)


def parse_env_line(raw_line: str) -> tuple[str, str] | None:
    line = raw_line.strip()
    if not line or line.startswith("#"):
        return None
    if line.startswith("export "):
        line = line[len("export ") :].strip()
    if "=" not in line:
        return None
    key, value = line.split("=", 1)
    key = key.strip()
    if not key or key[0].isdigit() or not key.replace("_", "").isalnum():
        return None
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return key, value


def parse_csv(value: str) -> list[str]:
    items = [item.strip() for item in value.split(",")]
    return [item for item in items if item]


def parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def parse_m30_preview_profile(value: str) -> str:
    profile = value.strip().lower() or "production"
    if profile not in {"production", "development"}:
        return "production"
    return profile
