from __future__ import annotations

import importlib
import os
import struct
import sys
import zlib
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient


def pytest_configure() -> None:
    os.environ["IMAGE_FIGMA_LOAD_LOCAL_ENV"] = "false"


@pytest.fixture(autouse=True)
def deterministic_test_environment(monkeypatch) -> Iterator[None]:
    monkeypatch.setenv("IMAGE_FIGMA_LOAD_LOCAL_ENV", "false")
    monkeypatch.setenv("OCR_PROVIDER", "fake")
    monkeypatch.setenv("VISUAL_PRIMITIVE_PROVIDER", "fake")
    monkeypatch.setenv("DSL_PATCH_MODE", "debug")
    monkeypatch.delenv("BAIDU_PADDLE_OCR_TOKEN", raising=False)
    monkeypatch.delenv("BAIDU_PADDLE_OCR_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    yield


@pytest.fixture()
def client(tmp_path, monkeypatch) -> Iterator[TestClient]:
    storage_root = tmp_path / "storage"
    monkeypatch.setenv("STORAGE_ROOT", str(storage_root))
    monkeypatch.setenv("DATABASE_PATH", str(storage_root / "app.db"))
    monkeypatch.setenv("PUBLIC_BASE_URL", "http://localhost:8000")

    for module_name in list(sys.modules):
        if module_name == "app" or module_name.startswith("app."):
            sys.modules.pop(module_name)

    main = importlib.import_module("app.main")
    with TestClient(main.create_app()) as test_client:
        yield test_client


@pytest.fixture()
def png_file() -> tuple[str, bytes, str]:
    return ("input.png", PNG_BYTES, "image/png")


def make_png(width: int, height: int) -> bytes:
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    row = b"\x00" + b"\x00" * (width * 3)
    idat_data = zlib.compress(row * height)
    return b"".join(
        [
            b"\x89PNG\r\n\x1a\n",
            png_chunk(b"IHDR", ihdr_data),
            png_chunk(b"IDAT", idat_data),
            png_chunk(b"IEND", b""),
        ]
    )


def png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    checksum = zlib.crc32(chunk_type)
    checksum = zlib.crc32(data, checksum)
    return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", checksum & 0xFFFFFFFF)


PNG_WIDTH = 317
PNG_HEIGHT = 2729
PNG_BYTES = make_png(PNG_WIDTH, PNG_HEIGHT)
