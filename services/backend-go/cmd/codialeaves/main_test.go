package main

import (
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
)

func TestCodiaLeavesCLIWritesArtifacts(t *testing.T) {
	tmp := t.TempDir()
	input := filepath.Join(tmp, "evidence_tokens.v1.json")
	out := filepath.Join(tmp, "out")
	if err := os.WriteFile(input, []byte(minimalEvidenceTokensJSON), 0o644); err != nil {
		t.Fatalf("write fixture: %v", err)
	}
	cmd := exec.Command("go", "run", ".", "-tokens", input, "-out", out)
	cmd.Dir = "."
	data, err := cmd.CombinedOutput()
	if err != nil {
		t.Fatalf("go run . failed: %v\n%s", err, string(data))
	}
	if !strings.Contains(string(data), "codia_leaf_ir.v1.json") || !strings.Contains(string(data), "codia_figma_like_tree.v1.json") {
		t.Fatalf("unexpected CLI output: %s", string(data))
	}
	for _, name := range []string{
		"codia_leaf_ir.v1.json",
		"codia_leaf_ir_report.md",
		"codia_figma_like_tree.v1.json",
	} {
		if _, err := os.Stat(filepath.Join(out, name)); err != nil {
			t.Fatalf("expected %s: %v", name, err)
		}
	}
}

const minimalEvidenceTokensJSON = `{
  "schemaName": "M29EvidenceTokens",
  "version": "1.0",
  "source": {
    "imageWidth": 100,
    "imageHeight": 200,
    "sourcePath": "sample.png"
  },
  "tokens": [
    {
      "id": "token_0001",
      "tokenType": "text_token",
      "bbox": {"x": 10, "y": 20, "width": 40, "height": 12},
      "content": {"text": "Hi"},
      "measurements": {"area": 480},
      "disposition": "main",
      "compileHints": {"confidence": 1}
    }
  ]
}`
