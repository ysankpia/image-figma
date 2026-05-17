from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


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


def get_settings() -> Settings:
    backend_root = Path(__file__).resolve().parents[1]
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
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_vision_model=os.getenv("OPENAI_VISION_MODEL", "gpt-5.5").strip() or "gpt-5.5",
        openai_timeout_seconds=float(os.getenv("OPENAI_TIMEOUT_SECONDS", "30")),
    )


def parse_csv(value: str) -> list[str]:
    items = [item.strip() for item in value.split(",")]
    return [item for item in items if item]


def parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}
