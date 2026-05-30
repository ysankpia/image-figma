package main

import (
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
)

func TestCodiaControlsCLIWritesArtifacts(t *testing.T) {
	tmp := t.TempDir()
	input := filepath.Join(tmp, "codia_leaf_ir.v1.json")
	out := filepath.Join(tmp, "out")
	if err := os.WriteFile(input, []byte(minimalLeafIRJSON), 0o644); err != nil {
		t.Fatalf("write fixture: %v", err)
	}
	cmd := exec.Command("go", "run", ".", "-input", input, "-out", out)
	cmd.Dir = "."
	data, err := cmd.CombinedOutput()
	if err != nil {
		t.Fatalf("go run . failed: %v\n%s", err, string(data))
	}
	if !strings.Contains(string(data), "codia_control_ir.v1.json") || !strings.Contains(string(data), "codia_figma_like_tree.v1.json") {
		t.Fatalf("unexpected CLI output: %s", string(data))
	}
	for _, name := range []string{
		"codia_control_stage.v1.json",
		"codia_control_ir.v1.json",
		"codia_control_ir_report.md",
		"codia_figma_like_tree.v1.json",
	} {
		if _, err := os.Stat(filepath.Join(out, name)); err != nil {
			t.Fatalf("expected %s: %v", name, err)
		}
	}
}

const minimalLeafIRJSON = `{
  "schemaName": "CodiaIR",
  "version": "1.0",
  "source": {"inputPath": "tokens"},
  "root": {
    "id": "root_0",
    "role": "root",
    "source_bbox": {"x": 0, "y": 0, "width": 100, "height": 200},
    "figma_bbox": {"x": 0, "y": 0, "width": 100, "height": 200},
    "figma_type": "FRAME",
    "visible_name": "Root",
    "children": [
      {
        "id": "bg",
        "role": "Background",
        "source_bbox": {"x": 10, "y": 20, "width": 70, "height": 32},
        "figma_bbox": {"x": 10, "y": 20, "width": 70, "height": 32},
        "figma_type": "ROUNDED_RECTANGLE",
        "visible_name": "Background",
        "evidence": [{"kind": "solid_background", "bbox": {"x": 10, "y": 20, "width": 70, "height": 32}, "confidence": 0.8}]
      },
      {
        "id": "text",
        "role": "TextView",
        "source_bbox": {"x": 24, "y": 27, "width": 38, "height": 16},
        "figma_bbox": {"x": 24, "y": 27, "width": 38, "height": 16},
        "figma_type": "TEXT",
        "visible_name": "Go",
        "text": {"characters": "Go"}
      }
    ]
  },
  "summary": {
    "nodeCount": 3,
    "maxDepth": 1,
    "roleCounts": {"root": 1, "Background": 1, "TextView": 1},
    "figmaTypeCounts": {"FRAME": 1, "ROUNDED_RECTANGLE": 1, "TEXT": 1}
  }
}`
