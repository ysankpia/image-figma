package main

import (
	"encoding/json"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/ir"
)

func TestCodiaDiffCLIWritesArtifacts(t *testing.T) {
	tmp := t.TempDir()
	generated := filepath.Join(tmp, "generated.json")
	golden := filepath.Join(tmp, "golden.json")
	out := filepath.Join(tmp, "out")
	writeFixture(t, generated, fixtureDoc("generated_text", "Hello"))
	writeFixture(t, golden, fixtureDoc("golden_text", "Hello"))

	cmd := exec.Command("go", "run", ".", "-generated", generated, "-golden", golden, "-out", out)
	cmd.Dir = "."
	data, err := cmd.CombinedOutput()
	if err != nil {
		t.Fatalf("go run . failed: %v\n%s", err, string(data))
	}
	if !strings.Contains(string(data), "matched 2") {
		t.Fatalf("unexpected CLI output: %s", string(data))
	}
	for _, name := range []string{"codia_structure_diff.v1.json", "codia_structure_diff_report.md"} {
		if _, err := os.Stat(filepath.Join(out, name)); err != nil {
			t.Fatalf("expected %s: %v", name, err)
		}
	}
}

func TestCodiaDiffCLIFailOnDiff(t *testing.T) {
	tmp := t.TempDir()
	generated := filepath.Join(tmp, "generated.json")
	golden := filepath.Join(tmp, "golden.json")
	out := filepath.Join(tmp, "out")
	writeFixture(t, generated, fixtureDoc("generated_text", "Hello"))
	goldenDoc := fixtureDoc("golden_text", "World")
	goldenDoc.Root.Children[0].SourceBBox.X = 70
	goldenDoc.Root.Children[0].FigmaBBox.X = 70
	writeFixture(t, golden, goldenDoc)

	cmd := exec.Command("go", "run", ".", "-generated", generated, "-golden", golden, "-out", out, "-fail-on-diff")
	cmd.Dir = "."
	data, err := cmd.CombinedOutput()
	if err == nil {
		t.Fatalf("expected fail-on-diff to exit non-zero:\n%s", string(data))
	}
	if !strings.Contains(string(data), "extra") || !strings.Contains(string(data), "missed") {
		t.Fatalf("expected diff counts in output, got:\n%s", string(data))
	}
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
