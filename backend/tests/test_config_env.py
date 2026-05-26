from __future__ import annotations

from pathlib import Path

import app.config as config


def test_local_env_loader_sets_missing_values_without_overriding(monkeypatch, tmp_path: Path) -> None:
    env_file = tmp_path / ".env.local"
    env_file.write_text(
        "\n".join(
            [
                "# local backend config",
                "OCR_PROVIDER=baidu_ppocrv5",
                "export BAIDU_PADDLE_OCR_TOKEN='local-token'",
                'BAIDU_PADDLE_OCR_MODEL="PP-OCRv5"',
                "IGNORED_LINE",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("OCR_PROVIDER", raising=False)
    monkeypatch.setenv("IMAGE_FIGMA_LOAD_LOCAL_ENV", "true")
    monkeypatch.setenv("BAIDU_PADDLE_OCR_TOKEN", "shell-token")
    monkeypatch.delenv("BAIDU_PADDLE_OCR_MODEL", raising=False)
    monkeypatch.setattr(config, "_LOCAL_ENV_LOADED", False)

    config.load_local_env_file(env_file)

    assert config.os.environ["OCR_PROVIDER"] == "baidu_ppocrv5"
    assert config.os.environ["BAIDU_PADDLE_OCR_TOKEN"] == "shell-token"
    assert config.os.environ["BAIDU_PADDLE_OCR_MODEL"] == "PP-OCRv5"


def test_parse_env_line_supports_export_quotes_and_rejects_invalid_keys() -> None:
    assert config.parse_env_line("export OCR_PROVIDER='baidu_ppocrv5'") == ("OCR_PROVIDER", "baidu_ppocrv5")
    assert config.parse_env_line('BAIDU_PADDLE_OCR_MODEL="PP-OCRv5"') == ("BAIDU_PADDLE_OCR_MODEL", "PP-OCRv5")
    assert config.parse_env_line("# comment") is None
    assert config.parse_env_line("1_BAD=value") is None


def test_local_env_loader_can_be_disabled(monkeypatch, tmp_path: Path) -> None:
    env_file = tmp_path / ".env.local"
    env_file.write_text("OCR_PROVIDER=baidu_ppocrv5\n", encoding="utf-8")
    monkeypatch.delenv("OCR_PROVIDER", raising=False)
    monkeypatch.setenv("IMAGE_FIGMA_LOAD_LOCAL_ENV", "false")
    monkeypatch.setattr(config, "_LOCAL_ENV_LOADED", False)

    config.load_local_env_file(env_file)

    assert "OCR_PROVIDER" not in config.os.environ


def test_get_settings_exposes_current_runtime_config(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("IMAGE_FIGMA_LOAD_LOCAL_ENV", "false")
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "storage"))
    monkeypatch.setenv("OCR_PROVIDER", "baidu_ppocrv5")
    monkeypatch.setenv("UPLOAD_PREVIEW_PROFILE", "development")
    monkeypatch.setenv("M29_PERCEPTION_MODEL_ENABLED", "true")
    monkeypatch.setenv("M29_PERCEPTION_MODEL_PATH", " /tmp/model.onnx ")
    monkeypatch.setattr(config, "_LOCAL_ENV_LOADED", False)

    settings = config.get_settings()

    assert settings.ocr_provider == "baidu_ppocrv5"
    assert settings.upload_preview_profile == "development"
    assert settings.m29_perception_model_enabled is True
    assert settings.m29_perception_model_path == "/tmp/model.onnx"


def test_parse_bool_supports_common_env_values() -> None:
    assert config.parse_bool("true", default=False) is True
    assert config.parse_bool("1", default=False) is True
    assert config.parse_bool("yes", default=False) is True
    assert config.parse_bool("false", default=True) is False
    assert config.parse_bool("0", default=True) is False
    assert config.parse_bool("off", default=True) is False
    assert config.parse_bool("", default=True) is True
    assert config.parse_bool("not-a-bool", default=False) is False


def test_normalized_optional_string_strips_empty_values() -> None:
    assert config.normalized_optional_string(None) is None
    assert config.normalized_optional_string("") is None
    assert config.normalized_optional_string("  ") is None
    assert config.normalized_optional_string(" /tmp/model.onnx ") == "/tmp/model.onnx"
