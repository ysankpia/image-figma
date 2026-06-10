HOST ?= 127.0.0.1
PORT ?= 8120
IMAGE ?=
OUT ?= /Volumes/WorkDrive/pencil-exports/handoff-acceptance

.PHONY: check test serve web-install web-typecheck web-test web-build handoff-acceptance

check: test web-typecheck web-test

test:
	uv run pytest -q

serve:
	uv run uvicorn app.main:app --host "$(HOST)" --port "$(PORT)"

web-install:
	cd web && pnpm install

web-typecheck:
	cd web && pnpm run typecheck

web-test:
	cd web && pnpm run test

web-build:
	cd web && pnpm run build

handoff-acceptance:
	uv run python scripts/handoff_acceptance.py --base-url "http://$(HOST):$(PORT)" --input "$(IMAGE)" --out "$(OUT)"
