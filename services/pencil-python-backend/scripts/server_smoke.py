from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import requests

SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVICE_ROOT.parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify a running Pencil Python Backend instance.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8100")
    parser.add_argument("--image", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--project-name", default="Pencil Server Smoke")
    parser.add_argument("--mode", default="all", choices=("all", "clean-editable", "visual-fidelity", "visual-ocr"))
    parser.add_argument("--expected-boundary-source", default="psdlike", choices=("m29", "psdlike", "hybrid"))
    parser.add_argument(
        "--expected-git-short-commit",
        help="Optional bundle/release git short commit expected for this smoke run.",
    )
    parser.add_argument("--timeout-seconds", type=float, default=180.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    base_url = args.base_url.rstrip("/")
    image = args.image.expanduser().resolve()
    if not image.exists():
        print(f"image does not exist: {image}", file=sys.stderr)
        return 2

    health = get_json(f"{base_url}/api/health")
    status = health.get("data", {}).get("status")
    if status != "ok":
        raise AssertionError(json.dumps(health, ensure_ascii=False, indent=2))
    print(f"health={status}")

    ready = get_json(f"{base_url}/api/ready")
    ready_data = ready.get("data", {})
    if ready_data.get("status") != "ready" or ready_data.get("ready") is not True:
        raise AssertionError(json.dumps(ready, ensure_ascii=False, indent=2))
    print("ready=ready")
    print_ready_checks(ready_data)

    if args.expected_git_short_commit:
        actual = git_short_commit()
        print(f"gitShortCommit={actual}")
        if actual != args.expected_git_short_commit:
            raise AssertionError(f"gitShortCommit={actual}, expected {args.expected_git_short_commit}")

    run_http_smoke(args, base_url, image)
    print("serverSmoke=ok")
    return 0


def get_json(url: str) -> dict[str, Any]:
    response = requests.get(url, timeout=10)
    try:
        body = response.json()
    except Exception:
        body = {"raw": response.text}
    if response.status_code != 200:
        raise AssertionError(json.dumps(body, ensure_ascii=False, indent=2))
    return body


def print_ready_checks(ready_data: dict[str, Any]) -> None:
    checks = ready_data.get("checks", [])
    if not isinstance(checks, list):
        return
    for check in checks:
        if not isinstance(check, dict):
            continue
        name = check.get("name")
        ok = "ok" if check.get("ok") else "fail"
        detail = check.get("detail", "")
        print(f"readyCheck.{name}={ok} {detail}")


def git_short_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git rev-parse failed")
    return result.stdout.strip()


def run_http_smoke(args: argparse.Namespace, base_url: str, image: Path) -> None:
    command = [
        sys.executable,
        "scripts/http_smoke.py",
        "--base-url",
        base_url,
        "--image",
        str(image),
        "--out",
        str(args.out.expanduser().resolve()),
        "--project-name",
        args.project_name,
        "--mode",
        args.mode,
        "--expected-boundary-source",
        args.expected_boundary_source,
        "--timeout-seconds",
        str(args.timeout_seconds),
    ]
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=SERVICE_ROOT, check=True)


if __name__ == "__main__":
    raise SystemExit(main())
