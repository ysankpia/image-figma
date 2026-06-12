from __future__ import annotations

import os
import subprocess
from pathlib import Path

from PIL import Image

from .types import M29RunResult


class M29RunnerError(RuntimeError):
    pass


def run_m29extract(
    *,
    image_path: Path,
    output_dir: Path,
    m29extract_path: Path | None,
    ocr_provider: str | None,
) -> M29RunResult:
    if m29extract_path is None:
        raise M29RunnerError("m29extract executable not found. Set PENCIL_BACKEND_M29EXTRACT.")
    if not m29extract_path.exists():
        raise M29RunnerError(f"m29extract executable does not exist: {m29extract_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    source_png = ensure_png_source(image_path, output_dir / "source.png")
    stdout_path = output_dir / "m29extract.stdout.txt"
    stderr_path = output_dir / "m29extract.stderr.txt"
    cmd = [str(m29extract_path), "-input", str(source_png), "-out", str(output_dir)]
    provider = (ocr_provider or "").strip()
    if provider:
        cmd.extend(["-ocr-provider", provider])

    env = os.environ.copy()
    result = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    stdout_path.write_text(result.stdout, encoding="utf-8")
    stderr_path.write_text(result.stderr, encoding="utf-8")
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit code {result.returncode}"
        raise M29RunnerError(f"m29extract failed for {image_path.name}: {detail}")
    evidence = output_dir / "m29_physical_evidence.v1.json"
    if not evidence.exists():
        raise M29RunnerError(f"m29extract did not write {evidence}")
    return M29RunResult(
        artifact_dir=output_dir,
        source_png=source_png,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
    )


def ensure_png_source(image_path: Path, target_path: Path) -> Path:
    source = image_path.expanduser().resolve()
    if source.suffix.lower() == ".png":
        if source != target_path:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_bytes(source.read_bytes())
        return target_path
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as image:
        image.convert("RGBA").save(target_path)
    return target_path
