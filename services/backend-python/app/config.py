from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class OCRConfig:
    token: str = ""
    job_url: str = "https://paddleocr.aistudio-app.com/api/v2/ocr/jobs"
    model: str = "PP-OCRv5"
    poll_interval: float = 5.0
    timeout: float = 120.0
    min_confidence: float = 0.7


@dataclass(frozen=True)
class OmniParserConfig:
    model_path: str = ""
    confidence: float = 0.3
    nms_iou: float = 0.5
    input_size: int = 640


@dataclass(frozen=True)
class VLMConfig:
    base_url: str = "https://aicode.cat"
    api_key: str = ""
    model: str = "gpt-5.5"
    timeout: float = 90.0
    min_confidence: float = 0.65
    transport_retries: int = 3


@dataclass(frozen=True)
class PlannerConfig:
    image_min_area: int = 400
    shape_min_area: int = 1200
    batch_max_candidates: int = 25
    text_overlap_suppress_ratio: float = 0.08


@dataclass(frozen=True)
class ServerConfig:
    port: int = 8000
    storage_root: str = "./storage"
    max_upload_bytes: int = 20 * 1024 * 1024


@dataclass(frozen=True)
class Config:
    ocr: OCRConfig = field(default_factory=OCRConfig)
    omniparser: OmniParserConfig = field(default_factory=OmniParserConfig)
    vlm: VLMConfig = field(default_factory=VLMConfig)
    planner: PlannerConfig = field(default_factory=PlannerConfig)
    server: ServerConfig = field(default_factory=ServerConfig)


def load_config() -> Config:
    return Config(
        ocr=OCRConfig(
            token=os.getenv("BAIDU_PADDLE_OCR_TOKEN", ""),
            job_url=os.getenv("BAIDU_PADDLE_OCR_JOB_URL", "https://paddleocr.aistudio-app.com/api/v2/ocr/jobs"),
            model=os.getenv("BAIDU_PADDLE_OCR_MODEL", "PP-OCRv5"),
            poll_interval=float(os.getenv("BAIDU_PADDLE_OCR_POLL_INTERVAL_SECONDS", "5")),
            timeout=float(os.getenv("BAIDU_PADDLE_OCR_TIMEOUT_SECONDS", "120")),
            min_confidence=float(os.getenv("OCR_MIN_CONFIDENCE", "0.7")),
        ),
        omniparser=OmniParserConfig(
            model_path=os.getenv("OMNIPARSER_MODEL_PATH", "/Volumes/WorkDrive/Models/model_fp16.onnx"),
            confidence=float(os.getenv("OMNIPARSER_CONFIDENCE", "0.3")),
            nms_iou=float(os.getenv("OMNIPARSER_NMS_IOU", "0.5")),
            input_size=int(os.getenv("OMNIPARSER_INPUT_SIZE", "640")),
        ),
        vlm=VLMConfig(
            base_url=os.getenv("VISION_BASE_URL", "https://aicode.cat"),
            api_key=os.getenv("VISION_API_KEY", os.getenv("CODIA_UI_DETECTOR_API_KEY", "")),
            model=os.getenv("VISION_MODEL", os.getenv("CODIA_UI_DETECTOR_MODEL", "gpt-5.5")),
            timeout=float(os.getenv("VISION_TIMEOUT_SECONDS", "90")),
            min_confidence=float(os.getenv("VLM_MIN_CONFIDENCE", "0.65")),
            transport_retries=int(os.getenv("VISION_TRANSPORT_RETRIES", "3")),
        ),
        planner=PlannerConfig(
            image_min_area=int(os.getenv("IMAGE_MIN_AREA", "400")),
            shape_min_area=int(os.getenv("SHAPE_MIN_AREA", "1200")),
            batch_max_candidates=int(os.getenv("BATCH_MAX_CANDIDATES", "25")),
            text_overlap_suppress_ratio=float(os.getenv("TEXT_OVERLAP_SUPPRESS_RATIO", "0.08")),
        ),
        server=ServerConfig(
            port=int(os.getenv("PIPELINE_SERVER_PORT", "8001")),
            storage_root=os.getenv("PIPELINE_STORAGE_ROOT", "./storage"),
            max_upload_bytes=int(os.getenv("PIPELINE_MAX_UPLOAD_BYTES", str(20 * 1024 * 1024))),
        ),
    )


def load_dotenv_local() -> None:
    """Load .env.local from ancestors, same logic as Go backend."""
    cwd = Path.cwd()
    for directory in [cwd, *cwd.parents]:
        env_file = directory / ".env.local"
        if env_file.is_file():
            for line in env_file.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                line = line.removeprefix("export ").strip()
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip("\"'")
                if key and key not in os.environ:
                    os.environ[key] = value
            break
