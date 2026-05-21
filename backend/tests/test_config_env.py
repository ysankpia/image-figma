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
    monkeypatch.setenv("M30_PREVIEW_PROFILE", "development")
    monkeypatch.setenv("M31_UPLOAD_DIAGNOSTICS_ENABLED", "false")
    monkeypatch.setenv("M31_UPLOAD_DIAGNOSTICS_STRICT", "true")
    monkeypatch.setenv("OCR_TEXT_EDITABILITY_ENABLED", "false")
    monkeypatch.setenv("OCR_GRAPHIC_TEXT_PRESERVE_ENABLED", "false")
    monkeypatch.setenv("OCR_TEXT_SYMBOL_LEAKAGE_CLEANUP_ENABLED", "false")
    monkeypatch.setenv("M30_SHAPE_ERASURE_ENABLED", "false")
    monkeypatch.setenv("M30_IMAGE_ERASURE_ENABLED", "false")
    monkeypatch.setenv("M30_ACCEPTED_IMAGE_MATERIALIZATION_ENABLED", "false")
    monkeypatch.setenv("M30_ACCEPTED_IMAGE_MAX_TEXT_OVERLAP", "0.03")
    monkeypatch.setenv("M30_ACCEPTED_IMAGE_MIN_AREA", "12345")
    monkeypatch.setenv("M30_IMAGE_ASSET_TEXT_ERASURE_ENABLED", "false")
    monkeypatch.setenv("M30_COMPOSITE_MEDIA_MATERIALIZATION_ENABLED", "false")
    monkeypatch.setenv("M30_COMPOSITE_MEDIA_MIN_AREA", "65432")
    monkeypatch.setenv("M38_HIERARCHY_MATERIALIZATION_ENABLED", "false")
    monkeypatch.setenv("M38_HIERARCHY_MATERIALIZATION_STRICT", "true")
    monkeypatch.setenv("M38_HIERARCHY_MAX_CONTAINERS", "3")
    monkeypatch.setattr(config, "_LOCAL_ENV_LOADED", False)

    settings = config.get_settings()

    assert settings.ocr_provider == "baidu_ppocrv5"
    assert settings.m30_preview_profile == "development"
    assert settings.m31_upload_diagnostics_enabled is False
    assert settings.m31_upload_diagnostics_strict is True
    assert settings.ocr_text_editability_enabled is False
    assert settings.ocr_graphic_text_preserve_enabled is False
    assert settings.ocr_text_symbol_leakage_cleanup_enabled is False
    assert settings.m30_shape_erasure_enabled is False
    assert settings.m30_image_erasure_enabled is False
    assert settings.m30_accepted_image_materialization_enabled is False
    assert settings.m30_accepted_image_max_text_overlap == 0.03
    assert settings.m30_accepted_image_min_area == 12345
    assert settings.m30_image_asset_text_erasure_enabled is False
    assert settings.m30_composite_media_materialization_enabled is False
    assert settings.m30_composite_media_min_area == 65432
    assert settings.m38_hierarchy_materialization_enabled is False
    assert settings.m38_hierarchy_materialization_strict is True
    assert settings.m38_hierarchy_max_containers == 3


def test_parse_bool_supports_common_env_values() -> None:
    assert config.parse_bool("true", default=False) is True
    assert config.parse_bool("1", default=False) is True
    assert config.parse_bool("yes", default=False) is True
    assert config.parse_bool("false", default=True) is False
    assert config.parse_bool("0", default=True) is False
    assert config.parse_bool("off", default=True) is False
    assert config.parse_bool("", default=True) is True
    assert config.parse_bool("not-a-bool", default=False) is False
