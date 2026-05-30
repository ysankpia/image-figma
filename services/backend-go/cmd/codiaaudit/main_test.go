package main

import (
	"encoding/json"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/diff"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/ir"
)

func TestCodiaAuditCLIWritesArtifacts(t *testing.T) {
	tmp := t.TempDir()
	diffPath := filepath.Join(tmp, "codia_structure_diff.v1.json")
	out := filepath.Join(tmp, "out")
	diffDoc, err := diff.Compare(
		fixtureDoc([]ir.Node{image("gen_image", 20, 20, 140, 100)}),
		fixtureDoc([]ir.Node{image("gold_image", 40, 40, 80, 60)}),
	)
	if err != nil {
		t.Fatalf("Compare() error = %v", err)
	}
	writeJSON(t, diffPath, diffDoc)

	cmd := exec.Command("go", "run", ".", "-diff", diffPath, "-out", out)
	cmd.Dir = "."
	data, err := cmd.CombinedOutput()
	if err != nil {
		t.Fatalf("go run . failed: %v\n%s", err, string(data))
	}
	if !strings.Contains(string(data), "codia_failure_audit.v1.json") {
		t.Fatalf("unexpected CLI output: %s", string(data))
	}
	for _, name := range []string{"codia_failure_audit.v1.json", "codia_failure_audit_report.md"} {
		if _, err := os.Stat(filepath.Join(out, name)); err != nil {
			t.Fatalf("expected %s: %v", name, err)
		}
	}
}

func TestCodiaAuditCLIMissingRequiredFlags(t *testing.T) {
	cmd := exec.Command("go", "run", ".")
	cmd.Dir = "."
	data, err := cmd.CombinedOutput()
	if err == nil {
		t.Fatalf("expected missing flags to fail:\n%s", string(data))
	}
	if !strings.Contains(string(data), "Usage") {
		t.Fatalf("expected usage output, got:\n%s", string(data))
	}
}

func fixtureDoc(children []ir.Node) ir.Document {
	root := ir.Node{
		ID:          "root_0",
		Role:        ir.RoleRoot,
		SourceBBox:  ir.BBox{X: 0, Y: 0, Width: 320, Height: 640},
		FigmaBBox:   ir.BBox{X: 0, Y: 0, Width: 320, Height: 640},
		FigmaType:   ir.FigmaFrame,
		VisibleName: "Root",
		SchemaID:    "root_0",
		Children:    children,
	}
	return ir.Document{
		SchemaName: ir.SchemaName,
		Version:    ir.Version,
		Root:       root,
		Summary:    ir.Summary{NodeCount: len(children) + 1},
	}
}

func image(id string, x int, y int, width int, height int) ir.Node {
	return ir.Node{
		ID:          id,
		Role:        ir.RoleImageView,
		SourceBBox:  ir.BBox{X: x, Y: y, Width: width, Height: height},
		FigmaBBox:   ir.BBox{X: x, Y: y, Width: width, Height: height},
		FigmaType:   ir.FigmaRoundedRectangle,
		VisibleName: "Image",
		SchemaID:    "ImageView_0_0_1",
		Evidence:    []ir.Evidence{{Kind: "image_crop", BBox: ir.BBox{X: x, Y: y, Width: width, Height: height}, Confidence: 0.7}},
	}
}

func writeJSON(t *testing.T, path string, value any) {
	t.Helper()
	data, err := json.MarshalIndent(value, "", "  ")
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	if err := os.WriteFile(path, data, 0o644); err != nil {
		t.Fatalf("write: %v", err)
	}
}
