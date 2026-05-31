package main

import (
	"encoding/json"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/eval/codia/ir"
)

func TestDraftEvalAnalyzeWritesArtifacts(t *testing.T) {
	tmp := t.TempDir()
	input := filepath.Join(tmp, "sample.canvas.json")
	out := filepath.Join(tmp, "out")
	if err := os.WriteFile(input, []byte(minimalCanvasJSON), 0o644); err != nil {
		t.Fatalf("write fixture: %v", err)
	}
	data := runDraftEval(t, "analyze", "-input", input, "-out", out)
	if !strings.Contains(data, "codia_ir.v1.json") {
		t.Fatalf("unexpected output: %s", data)
	}
	for _, name := range []string{
		"codia_canvas_analysis.v1.json",
		"codia_canvas_analysis_report.md",
		"codia_ir.v1.json",
	} {
		if _, err := os.Stat(filepath.Join(out, name)); err != nil {
			t.Fatalf("expected %s: %v", name, err)
		}
	}
}

func TestDraftEvalDiffAndAuditWriteArtifacts(t *testing.T) {
	tmp := t.TempDir()
	generated := filepath.Join(tmp, "generated.json")
	golden := filepath.Join(tmp, "golden.json")
	diffOut := filepath.Join(tmp, "diff")
	auditOut := filepath.Join(tmp, "audit")
	writeFixture(t, generated, fixtureDoc("generated_text", "Hello"))
	writeFixture(t, golden, fixtureDoc("golden_text", "Hello"))

	diffOutput := runDraftEval(t, "diff", "-generated", generated, "-golden", golden, "-out", diffOut)
	if !strings.Contains(diffOutput, "matched 2") {
		t.Fatalf("unexpected diff output: %s", diffOutput)
	}
	for _, name := range []string{"codia_structure_diff.v1.json", "codia_structure_diff_report.md"} {
		if _, err := os.Stat(filepath.Join(diffOut, name)); err != nil {
			t.Fatalf("expected %s: %v", name, err)
		}
	}

	auditOutput := runDraftEval(t, "audit", "-diff", filepath.Join(diffOut, "codia_structure_diff.v1.json"), "-out", auditOut)
	if !strings.Contains(auditOutput, "codia_failure_audit.v1.json") {
		t.Fatalf("unexpected audit output: %s", auditOutput)
	}
	for _, name := range []string{"codia_failure_audit.v1.json", "codia_failure_audit_report.md"} {
		if _, err := os.Stat(filepath.Join(auditOut, name)); err != nil {
			t.Fatalf("expected %s: %v", name, err)
		}
	}
}

func TestDraftEvalMissingSubcommandFails(t *testing.T) {
	cmd := exec.Command("go", "run", ".")
	cmd.Dir = "."
	data, err := cmd.CombinedOutput()
	if err == nil {
		t.Fatalf("expected missing subcommand to fail:\n%s", string(data))
	}
	if !strings.Contains(string(data), "usage: drafteval") {
		t.Fatalf("expected usage output, got:\n%s", string(data))
	}
}

func runDraftEval(t *testing.T, args ...string) string {
	t.Helper()
	cmd := exec.Command("go", append([]string{"run", "."}, args...)...)
	cmd.Dir = "."
	data, err := cmd.CombinedOutput()
	if err != nil {
		t.Fatalf("go run . %s failed: %v\n%s", strings.Join(args, " "), err, string(data))
	}
	return string(data)
}

func fixtureDoc(textID string, value string) ir.Document {
	root := ir.Node{
		ID:          "root_0",
		Role:        ir.RoleRoot,
		SourceBBox:  ir.BBox{X: 0, Y: 0, Width: 100, Height: 100},
		FigmaBBox:   ir.BBox{X: 0, Y: 0, Width: 100, Height: 100},
		FigmaType:   ir.FigmaFrame,
		VisibleName: "Root",
		SchemaID:    "root_0",
		Children: []ir.Node{
			{
				ID:          textID,
				Role:        ir.RoleTextView,
				SourceBBox:  ir.BBox{X: 10, Y: 20, Width: 50, Height: 20},
				FigmaBBox:   ir.BBox{X: 10, Y: 20, Width: 50, Height: 20},
				FigmaType:   ir.FigmaText,
				VisibleName: value,
				SchemaID:    "TextView_10_20_1",
				Text:        &ir.Text{Characters: value},
			},
		},
	}
	return ir.Document{
		SchemaName: ir.SchemaName,
		Version:    ir.Version,
		Root:       root,
		Summary: ir.Summary{
			NodeCount:       2,
			MaxDepth:        1,
			RoleCounts:      map[string]int{"root": 1, "TextView": 1},
			FigmaTypeCounts: map[string]int{"FRAME": 1, "TEXT": 1},
		},
	}
}

func writeFixture(t *testing.T, path string, doc ir.Document) {
	t.Helper()
	data, err := json.MarshalIndent(doc, "", "  ")
	if err != nil {
		t.Fatalf("marshal fixture: %v", err)
	}
	if err := os.WriteFile(path, data, 0o644); err != nil {
		t.Fatalf("write fixture: %v", err)
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
