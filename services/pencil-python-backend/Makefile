SHELL := /bin/sh

SERVICE_DIR := $(shell pwd)
BIN_DIR ?= $(HOME)/.local/bin
COMMAND ?= pencil-export

.PHONY: install-local
install-local:
	mkdir -p "$(BIN_DIR)"
	printf '%s\n' '#!/bin/sh' \
		'cd "$(SERVICE_DIR)" || exit 1' \
		'exec uv run python -m app.cli.export_project "$$@"' \
		> "$(BIN_DIR)/$(COMMAND)"
	chmod +x "$(BIN_DIR)/$(COMMAND)"
	@echo "Installed $(COMMAND) to $(BIN_DIR)/$(COMMAND)"
