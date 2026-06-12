from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVICE_ROOT.parents[1]

INCLUDE_PREFIXES = (
    "services/pencil-python-backend/",
    "services/psdlike-python/",
    "services/backend-go/cmd/m29extract/",
    "services/backend-go/internal/m29/",
)

INCLUDE_FILES = {
    "services/backend-go/go.mod",
    "docs/reference/env-vars.md",
    "docs/reference/pencil-python-backend-api.md",
    "docs/runbooks/pencil-python-backend-deploy.md",
    "docs/runbooks/pencil-python-backend-handoff.md",
}

FORBIDDEN_PARTS = {
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "storage",
    "dist",
    "build",
    "bin",
    ".DS_Store",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a clean deploy source bundle for Pencil Python Backend.")
    parser.add_argument(
        "--out",
        required=True,
        type=Path,
        help="Output directory for staging, archive, and manifest.",
    )
    parser.add_argument(
        "--name",
        default="pencil-python-backend-deploy",
        help="Bundle directory/archive base name.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Remove an existing staging directory or archive under --out.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out_dir = args.out.expanduser().resolve()
    staging_dir = out_dir / args.name
    archive_path = out_dir / f"{args.name}.tar.gz"
    manifest_path = out_dir / "bundle-manifest.json"
    summary_path = out_dir / "release-summary.md"

    if not is_git_repo():
        print(f"not a git repository: {REPO_ROOT}", file=sys.stderr)
        return 2

    if staging_dir.exists() or archive_path.exists():
        if not args.force:
            print(f"output already exists; rerun with --force: {staging_dir} or {archive_path}", file=sys.stderr)
            return 2
        if staging_dir.exists():
            shutil.rmtree(staging_dir)
        if archive_path.exists():
            archive_path.unlink()

    out_dir.mkdir(parents=True, exist_ok=True)
    files = select_files(git_ls_files())
    if not files:
        print("no files selected for bundle", file=sys.stderr)
        return 1

    for rel_path in files:
        copy_file(rel_path, staging_dir)

    create_archive(staging_dir, archive_path)
    archive_sha256 = sha256_file(archive_path)
    manifest = build_manifest(args.name, staging_dir, archive_path, archive_sha256, files)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary_path.write_text(build_release_summary(manifest), encoding="utf-8")

    print(f"staging={staging_dir}")
    print(f"archive={archive_path} bytes={archive_path.stat().st_size}")
    print(f"archiveSha256={archive_sha256}")
    print(f"manifest={manifest_path}")
    print(f"summary={summary_path}")
    print(f"files={len(files)}")
    return 0


def is_git_repo() -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return result.returncode == 0 and result.stdout.strip() == "true"


def git_ls_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git ls-files failed")
    return [line for line in result.stdout.splitlines() if line]


def select_files(paths: Iterable[str]) -> list[str]:
    selected = []
    for rel_path in paths:
        if not is_included(rel_path):
            continue
        if has_forbidden_part(rel_path):
            continue
        selected.append(rel_path)
    return sorted(selected)


def is_included(rel_path: str) -> bool:
    if rel_path in INCLUDE_FILES:
        return True
    return any(rel_path.startswith(prefix) for prefix in INCLUDE_PREFIXES)


def has_forbidden_part(rel_path: str) -> bool:
    return any(part in FORBIDDEN_PARTS for part in Path(rel_path).parts)


def copy_file(rel_path: str, staging_dir: Path) -> None:
    src = REPO_ROOT / rel_path
    dst = staging_dir / rel_path
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def create_archive(staging_dir: Path, archive_path: Path) -> None:
    with tarfile.open(archive_path, "w:gz") as archive:
        archive.add(staging_dir, arcname=staging_dir.name)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(
    bundle_name: str,
    staging_dir: Path,
    archive_path: Path,
    archive_sha256: str,
    files: list[str],
) -> dict[str, object]:
    commit = git_output(["git", "rev-parse", "HEAD"])
    short_commit = git_output(["git", "rev-parse", "--short", "HEAD"])
    return {
        "schema": "pencil.deploy_bundle.v1",
        "bundleName": bundle_name,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "repoRoot": str(REPO_ROOT),
        "gitCommit": commit,
        "gitShortCommit": short_commit,
        "stagingDir": str(staging_dir),
        "archivePath": str(archive_path),
        "archiveSha256": archive_sha256,
        "fileCount": len(files),
        "includedRoots": [
            "services/pencil-python-backend",
            "services/psdlike-python",
            "services/backend-go/cmd/m29extract",
            "services/backend-go/internal/m29",
            "docs/reference",
            "docs/runbooks",
        ],
        "excludedByConstruction": sorted(FORBIDDEN_PARTS),
        "serverBuildSteps": [
            "cd services/pencil-python-backend && uv sync",
            "cd services/psdlike-python && uv sync",
            "cd services/backend-go && mkdir -p bin && go build -o bin/m29extract ./cmd/m29extract",
            "cd services/pencil-python-backend && uv run python scripts/preflight.py --require-m29",
        ],
        "files": files,
    }


def build_release_summary(manifest: dict[str, object]) -> str:
    steps = manifest["serverBuildSteps"]
    if not isinstance(steps, list):
        raise TypeError("serverBuildSteps must be a list")
    step_text = "\n".join(f"- `{step}`" for step in steps)
    return f"""# Pencil Python Backend Deploy Bundle

```text
bundleName={manifest["bundleName"]}
gitShortCommit={manifest["gitShortCommit"]}
fileCount={manifest["fileCount"]}
archivePath={manifest["archivePath"]}
archiveSha256={manifest["archiveSha256"]}
```

## Verify After Upload

```bash
sha256sum pencil-python-backend-deploy.tar.gz
shasum -a 256 pencil-python-backend-deploy.tar.gz
```

Use either command depending on the server OS. The hash must match `archiveSha256` above.

## Server Build Steps

{step_text}
"""


def git_output(command: list[str]) -> str:
    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"{command} failed")
    return result.stdout.strip()


if __name__ == "__main__":
    raise SystemExit(main())
