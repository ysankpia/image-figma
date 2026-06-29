#!/usr/bin/env python3
from __future__ import annotations

import sys
import os
from pathlib import Path


def load_skill_env(skill_root: Path) -> None:
    env_path = skill_root / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def main() -> int:
    script_dir = Path(__file__).resolve().parent
    skill_root = script_dir.parent
    load_skill_env(skill_root)
    bundled_package = script_dir / "ui_rebuilder"
    if bundled_package.exists():
        sys.path.insert(0, str(script_dir))
    else:
        project_root = Path(__file__).resolve().parents[3]
        sys.path.insert(0, str(project_root / "src"))
    from ui_rebuilder.cli import main as cli_main

    return cli_main(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
