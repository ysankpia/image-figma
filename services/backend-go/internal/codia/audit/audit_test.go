package audit

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/diff"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/ir"
)

func TestAnalyzeGroupsFailuresByOwningLayer(t *testing.T) {
	generated := docWithRoot([]ir.Node{
		image("large_image", 20, 20, 140, 100),
		background("fragment_bg", 25, 30, 50, 20, "control_surface_background"),
	})
	golden := docWithRoot([]ir.Node{
		image("gold_crop", 40, 40, 80, 60),
		background("gold_bg", 200, 200, 80, 40, "golden_canvas_node"),
	})
	diffDoc, err := diff.Compare(generated, golden)
	if err != nil {
		t.Fatalf("Compare() error = %v", err)
	}
	out := Analyze(diffDoc)
	if out.SchemaName != SchemaName || out.Summary.ExtraNodeCount == 0 || out.Summary.MissedNodeCount == 0 {
		t.Fatalf("unexpected audit summary: %#v", out)
	}
	if out.Summary.ByStage["leaf_or_background"] == 0 {
		t.Fatalf("expected leaf/background failures: %#v", out.Summary.ByStage)
	}
	if out.Summary.ByDiagnosis["leaf_bbox_too_large_or_shifted"] == 0 {
		t.Fatalf("expected generated large image vs golden crop diagnosis: %#v", out.Summary.ByDiagnosis)
	}
	if out.Summary.ByDiagnosis["background_fragment_extra"] == 0 {
		t.Fatalf("expected background fragment extra diagnosis: %#v", out.Summary.ByDiagnosis)
	}
	if len(out.Actions) == 0 || out.Actions[0].OwnerLayer == "" {
		t.Fatalf("expected actionable owner layers: %#v", out.Actions)
	}
}

func TestCompileReadsDiffAndWritesArtifacts(t *testing.T) {
	tmp := t.TempDir()
	diffPath := filepath.Join(tmp, "codia_structure_diff.v1.json")
	generated := docWithRoot([]ir.Node{text("gen_extra", 60, 10, 40, 20, "Extra")})
	golden := docWithRoot([]ir.Node{text("gold_missed", 120, 10, 40, 20, "Missed")})
	diffDoc, err := diff.Compare(generated, golden)
	if err != nil {
		t.Fatalf("Compare() error = %v", err)
	}
	diffDoc.Source.GeneratedPath = "generated.json"
	diffDoc.Source.GoldenPath = "golden.json"
	writeJSON(t, diffPath, diffDoc)

	out, err := Compile(Options{DiffPath: diffPath})
	if err != nil {
		t.Fatalf("Compile() error = %v", err)
	}
	if out.Source.DiffPath != diffPath || out.Source.GeneratedPath != "generated.json" {
		t.Fatalf("expected source paths preserved: %#v", out.Source)
	}
	if err := WriteArtifacts(tmp, out); err != nil {
		t.Fatalf("WriteArtifacts() error = %v", err)
	}
	for _, name := range []string{"codia_failure_audit.v1.json", "codia_failure_audit_report.md"} {
		if _, err := os.Stat(filepath.Join(tmp, name)); err != nil {
			t.Fatalf("expected artifact %s: %v", name, err)
		}
	}
}

func docWithRoot(children []ir.Node) ir.Document {
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
		Summary:    summarize(root),
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

func background(id string, x int, y int, width int, height int, evidence string) ir.Node {
	return ir.Node{
		ID:          id,
		Role:        ir.RoleBackground,
		SourceBBox:  ir.BBox{X: x, Y: y, Width: width, Height: height},
		FigmaBBox:   ir.BBox{X: x, Y: y, Width: width, Height: height},
		FigmaType:   ir.FigmaRoundedRectangle,
		VisibleName: "Background",
		SchemaID:    "Background_0_0_1",
		Evidence:    []ir.Evidence{{Kind: evidence, BBox: ir.BBox{X: x, Y: y, Width: width, Height: height}, Confidence: 0.7}},
	}
}

func text(id string, x int, y int, width int, height int, value string) ir.Node {
	return ir.Node{
		ID:          id,
		Role:        ir.RoleTextView,
		SourceBBox:  ir.BBox{X: x, Y: y, Width: width, Height: height},
		FigmaBBox:   ir.BBox{X: x, Y: y, Width: width, Height: height},
		FigmaType:   ir.FigmaText,
		VisibleName: value,
		SchemaID:    "TextView_0_0_1",
		Text:        &ir.Text{Characters: value},
		Evidence:    []ir.Evidence{{Kind: "ocr_text", BBox: ir.BBox{X: x, Y: y, Width: width, Height: height}, Confidence: 1}},
	}
}

func summarize(root ir.Node) ir.Summary {
	roleCounts := map[string]int{}
	typeCounts := map[string]int{}
	maxDepth := 0
	count := 0
	var walk func(ir.Node, int)
	walk = func(node ir.Node, depth int) {
		count++
		roleCounts[string(node.Role)]++
		typeCounts[string(node.FigmaType)]++
		if depth > maxDepth {
			maxDepth = depth
		}
		for _, child := range node.Children {
			walk(child, depth+1)
		}
	}
	walk(root, 0)
	return ir.Summary{NodeCount: count, MaxDepth: maxDepth, RoleCounts: roleCounts, FigmaTypeCounts: typeCounts}
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
