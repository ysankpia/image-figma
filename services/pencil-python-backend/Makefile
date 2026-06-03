SHELL := /bin/sh

SERVICE_DIR := $(shell pwd)
BIN_DIR ?= $(HOME)/.local/bin
COMMAND ?= pencil-export
HOST ?= 127.0.0.1
PORT ?= 8100
BASE_URL ?= http://$(HOST):$(PORT)
IMAGE ?=
OUT ?= /tmp/pencil-http-output
PROJECT_NAME ?= Pencil HTTP Project
MODE ?= all
BUNDLE_OUT ?= /Volumes/WorkDrive/pencil-exports/pencil-backend-bundle
BUNDLE_ARCHIVE ?= $(BUNDLE_OUT)/pencil-python-backend-deploy.tar.gz

.PHONY: install-local check preflight preflight-strict serve smoke server-smoke upload-http acceptance bundle verify-bundle
install-local:
	mkdir -p "$(BIN_DIR)"
	printf '%s\n' '#!/bin/sh' \
		'cd "$(SERVICE_DIR)" || exit 1' \
		'exec uv run python -m app.cli.export_project "$$@"' \
		> "$(BIN_DIR)/$(COMMAND)"
	chmod +x "$(BIN_DIR)/$(COMMAND)"
	@echo "Installed $(COMMAND) to $(BIN_DIR)/$(COMMAND)"

check:
	uv run python -m py_compile $$(find app tests scripts -name '*.py' | sort)
	uv run pytest -q

preflight:
	PENCIL_BACKEND_DEFAULT_BOUNDARY_SOURCE=psdlike uv run python scripts/preflight.py

preflight-strict:
	PENCIL_BACKEND_DEFAULT_BOUNDARY_SOURCE=psdlike uv run python scripts/preflight.py --require-m29

serve:
	PENCIL_BACKEND_DEFAULT_BOUNDARY_SOURCE=psdlike uv run uvicorn app.main:app --host "$(HOST)" --port "$(PORT)"

smoke:
	@test -n "$(IMAGE)" || (echo "IMAGE=/absolute/path/to/sample.png is required" >&2; exit 2)
	uv run python scripts/http_smoke.py --base-url "$(BASE_URL)" --image "$(IMAGE)" --out "$(OUT)"

server-smoke:
	@test -n "$(IMAGE)" || (echo "IMAGE=/absolute/path/to/sample.png is required" >&2; exit 2)
	uv run python scripts/server_smoke.py --base-url "$(BASE_URL)" --image "$(IMAGE)" --out "$(OUT)" --project-name "$(PROJECT_NAME)" --mode "$(MODE)"

upload-http:
	@test -n "$(IMAGE)" || (echo "IMAGE=/absolute/path/to/image-or-dir is required" >&2; exit 2)
	uv run python scripts/upload_project.py --base-url "$(BASE_URL)" --input "$(IMAGE)" --out "$(OUT)" --project-name "$(PROJECT_NAME)" --mode "$(MODE)"

acceptance:
	@test -n "$(IMAGE)" || (echo "IMAGE=/absolute/path/to/sample.png is required" >&2; exit 2)
	uv run python scripts/local_acceptance.py --host "$(HOST)" --port "$(PORT)" --image "$(IMAGE)" --out "$(OUT)" --project-name "$(PROJECT_NAME)"

bundle:
	uv run python scripts/build_deploy_bundle.py --out "$(BUNDLE_OUT)" --force

verify-bundle: bundle
	@if [ -n "$(IMAGE)" ]; then \
		uv run python scripts/verify_deploy_bundle.py --archive "$(BUNDLE_ARCHIVE)" --acceptance-image "$(IMAGE)"; \
	else \
		uv run python scripts/verify_deploy_bundle.py --archive "$(BUNDLE_ARCHIVE)"; \
	fi
