from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from .m29_runner import ensure_png_source


class PSDLikeRunnerError(RuntimeError):
    pass


@dataclass(frozen=True)
class PSDLikeRunResult:
    artifact_dir: Path
    source_png: Path
    stdout_path: Path
    stderr_path: Path


def default_psdlike_root() -> Path:
    return Path(__file__).resolve().parents[3] / "services" / "psdlike-python"


def run_psdlike(
    *,
    image_path: Path,
    output_dir: Path,
    ocr_provider: str | None,
    psdlike_root: Path | None = None,
    tile_size: int = 8,
) -> PSDLikeRunResult:
    root = (psdlike_root or default_psdlike_root()).expanduser().resolve()
    script = root / "tools" / "run_one.py"
    if not script.exists():
        raise PSDLikeRunnerError(f"PSD-like runner not found: {script}")

    output_dir.mkdir(parents=True, exist_ok=True)
    source_png = ensure_png_source(image_path, output_dir / "source.png")
    stdout_path = output_dir / "psdlike.stdout.txt"
    stderr_path = output_dir / "psdlike.stderr.txt"
    cmd = [
        *resolve_psdlike_python_command(root),
        str(script),
        "--image",
        str(source_png),
        "--out",
        str(output_dir),
        "--tile-size",
        str(tile_size),
    ]
    provider = (ocr_provider or "").strip().lower()
    if provider and provider != "none":
        cmd.append("--run-ocr")
    else:
        cmd.append("--allow-missing-ocr")

    env = os.environ.copy()
    if provider:
        env["OCR_PROVIDER"] = provider
    result = subprocess.run(
        cmd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        cwd=str(root),
    )
    stdout_path.write_text(result.stdout, encoding="utf-8")
    stderr_path.write_text(result.stderr, encoding="utf-8")
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit code {result.returncode}"
        raise PSDLikeRunnerError(f"PSD-like pipeline failed for {image_path.name}: {detail}")
    layer_stack = output_dir / "layer_stack.v1.json"
    if not layer_stack.exists():
        raise PSDLikeRunnerError(f"PSD-like pipeline did not write {layer_stack}")
    return PSDLikeRunResult(
        artifact_dir=output_dir,
        source_png=source_png,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
    )


def resolve_psdlike_python_command(root: Path) -> list[str]:
    uv = shutil.which("uv")
    if uv:
        return [uv, "run", "python"]
    candidates = [
        root / ".venv" / "bin" / "python",
        root / ".venv" / "Scripts" / "python.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return [str(candidate.resolve())]
    return [str(Path(sys.executable).resolve())]
