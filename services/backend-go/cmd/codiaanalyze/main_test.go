package main

import (
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
)

func TestCodiaAnalyzeCLIWritesArtifacts(t *testing.T) {
	tmp := t.TempDir()
	input := filepath.Join(tmp, "sample.canvas.json")
	out := filepath.Join(tmp, "out")
	if err := os.WriteFile(input, []byte(minimalCanvasJSON), 0o644); err != nil {
		t.Fatalf("write fixture: %v", err)
	}
	cmd := exec.Command("go", "run", ".", "-input", input, "-out", out)
	cmd.Dir = "."
	data, err := cmd.CombinedOutput()
	if err != nil {
		t.Fatalf("go run . failed: %v\n%s", err, string(data))
	}
	if !strings.Contains(string(data), "1 nodes") {
		t.Fatalf("unexpected CLI output: %s", string(data))
	}
	for _, name := range []string{
		"codia_canvas_analysis.v1.json",
		"codia_canvas_analysis_report.md",
		"codia_ir.v1.json",
		"codia_figma_like_tree.v1.json",
	} {
		if _, err := os.Stat(filepath.Join(out, name)); err != nil {
			t.Fatalf("expected %s: %v", name, err)
		}
	}
}

func TestCodiaAnalyzeCLIExpectationFailureExitsNonZero(t *testing.T) {
	tmp := t.TempDir()
	input := filepath.Join(tmp, "sample.canvas.json")
	out := filepath.Join(tmp, "out")
	if err := os.WriteFile(input, []byte(minimalCanvasJSON), 0o644); err != nil {
		t.Fatalf("write fixture: %v", err)
	}
	cmd := exec.Command("go", "run", ".", "-input", input, "-out", out, "-expect", "tencent-comic-018")
	cmd.Dir = "."
	data, err := cmd.CombinedOutput()
	if err == nil {
		t.Fatalf("expected expectation failure, got success:\n%s", string(data))
	}
	if !strings.Contains(string(data), "expectation") || !strings.Contains(string(data), "failed") {
		t.Fatalf("expected clear expectation failure, got:\n%s", string(data))
	}
}

const minimalCanvasJSON = `{
  "version": 101,
  "root": {
    "type": "DOCUMENT",
    "name": "Document",
    "children": [
      {
        "type": "CANVAS",
        "name": "Page 1",
        "children": [
          {
            "type": "FRAME",
            "name": "Figma design - sample.png",
            "children": [
              {
                "guid": {"sessionID": 1, "localID": 1},
                "type": "FRAME",
                "name": "Root",
                "size": {"x": 100, "y": 100},
                "pluginData": [{"pluginID": "1329812760871373657", "key": "schema:id", "value": "root_0"}]
              }
            ]
          }
        ]
      }
    ]
  }
}`
