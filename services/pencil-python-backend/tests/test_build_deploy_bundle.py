from __future__ import annotations

from scripts.build_deploy_bundle import select_files


def test_select_files_keeps_deploy_sources_and_drops_local_artifacts() -> None:
    files = [
        "services/pencil-python-backend/app/main.py",
        "services/pencil-python-backend/.venv/lib/python/site.py",
        "services/pencil-python-backend/storage/tasks/task.json",
        "services/psdlike-python/tools/run_one.py",
        "services/psdlike-python/__pycache__/x.pyc",
        "services/backend-go/go.mod",
        "services/backend-go/cmd/m29extract/main.go",
        "services/backend-go/internal/m29/pipeline/pipeline.go",
        "services/backend-go/bin/m29extract",
        "services/backend-go/internal/draft/compile/compile.go",
        "docs/reference/pencil-python-backend-api.md",
        "docs/runbooks/pencil-python-backend-deploy.md",
        "figma-plugin/src/main.ts",
    ]

    assert select_files(files) == [
        "docs/reference/pencil-python-backend-api.md",
        "docs/runbooks/pencil-python-backend-deploy.md",
        "services/backend-go/cmd/m29extract/main.go",
        "services/backend-go/go.mod",
        "services/backend-go/internal/m29/pipeline/pipeline.go",
        "services/pencil-python-backend/app/main.py",
        "services/psdlike-python/tools/run_one.py",
    ]

