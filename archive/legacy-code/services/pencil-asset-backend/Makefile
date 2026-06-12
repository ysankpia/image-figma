SHELL := /bin/sh

HOST ?= 127.0.0.1
PORT ?= 8110
BASE_URL ?= http://$(HOST):$(PORT)
IMAGE ?=
OUT ?= /tmp/pencil-asset-acceptance
PROJECT_NAME ?= Pencil Asset Project

.PHONY: check serve asset-acceptance

check:
	uv run python -m py_compile $$(find app tests scripts -name '*.py' | sort)
	uv run pytest -q

serve:
	uv run uvicorn app.main:app --host "$(HOST)" --port "$(PORT)"

asset-acceptance:
	@test -n "$(IMAGE)" || (echo "IMAGE=/absolute/path/to/image-or-dir is required" >&2; exit 2)
	uv run python scripts/asset_acceptance.py --base-url "$(BASE_URL)" --input "$(IMAGE)" --out "$(OUT)" --project-name "$(PROJECT_NAME)"
