package diff

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/ir"
)

func TestCompareReportsMatchedExtraMissedAndChecks(t *testing.T) {
	golden := docWithRoot([]ir.Node{
		button("gold_button", 10, 10, 100, 40, "Pay"),
		text("gold_title", 10, 70, 80, 20, "Title"),
	})
	generated := docWithRoot([]ir.Node{
		button("gen_button", 10, 10, 100, 40, "Pay"),
		text("gen_extra", 220, 70, 80, 20, "Extra"),
	})
	out, err := Compare(generated, golden)
	if err != nil {
		t.Fatalf("Compare() error = %v", err)
	}
	if out.Summary.MatchedNodeCount != 4 {
		t.Fatalf("expected root, button, button text, bg matched; summary=%#v", out.Summary)
	}
	if out.Summary.ExtraNodeCount != 1 || out.Summary.MissedNodeCount != 1 {
		t.Fatalf("expected generated extra text and golden title missed; summary=%#v", out.Summary)
	}
	if !out.Checks.VisibleVocabularyPass {
		t.Fatalf("expected visible vocabulary pass: %#v", out.Checks.VisibleVocabularyViolations)
	}
	if !out.Checks.ButtonBackgroundLast.Pass || out.Checks.ButtonBackgroundLast.Passed != 1 {
		t.Fatalf("expected button background last pass: %#v", out.Checks.ButtonBackgroundLast)
	}
	if out.Summary.RoleMetrics[string(ir.RoleButton)].Precision != 1 || out.Summary.RoleMetrics[string(ir.RoleButton)].Recall != 1 {
		t.Fatalf("expected button role metrics to match: %#v", out.Summary.RoleMetrics[string(ir.RoleButton)])
	}
	if out.Summary.ExtraByEvidence["test_text"] != 1 || out.Summary.MissedByEvidence["test_text"] != 1 {
		t.Fatalf("expected evidence breakdown for text extra/missed: extra=%#v missed=%#v", out.Summary.ExtraByEvidence, out.Summary.MissedByEvidence)
	}
	for _, node := range out.Generated {
		if node.ID == "gen_extra" && node.EvidenceKind == "" {
			t.Fatalf("expected generated node evidence kind to be preserved: %#v", node)
		}
	}
}

func TestCompareDetectsInvalidVisibleNameAndButtonBackgroundOrder(t *testing.T) {
	golden := docWithRoot([]ir.Node{
		button("gold_button", 10, 10, 100, 40, "Pay"),
	})
	badButton := ir.Node{
		ID:          "bad_button",
		Role:        ir.RoleButton,
		SourceBBox:  ir.BBox{X: 10, Y: 10, Width: 100, Height: 40},
		FigmaBBox:   ir.BBox{X: 10, Y: 10, Width: 100, Height: 40},
		FigmaType:   ir.FigmaFrame,
		VisibleName: "Wrong",
		SchemaID:    "Button_10_10_1",
		Children: []ir.Node{
			bgButton("bad_button_bg", 10, 10, 100, 40),
			text("bad_button_text", 30, 20, 40, 16, "Pay"),
		},
	}
	generated := docWithRoot([]ir.Node{badButton})
	out, err := Compare(generated, golden)
	if err != nil {
		t.Fatalf("Compare() error = %v", err)
	}
	if out.Checks.VisibleVocabularyPass {
		t.Fatalf("expected visible vocabulary failure")
	}
	if out.Checks.ButtonBackgroundLast.Pass {
		t.Fatalf("expected bg_Button last-child failure")
	}
}

func TestCompileReadsIRAndWriteArtifacts(t *testing.T) {
	tmp := t.TempDir()
	generatedPath := filepath.Join(tmp, "generated.json")
	goldenPath := filepath.Join(tmp, "golden.json")
	writeIRFixture(t, generatedPath, docWithRoot([]ir.Node{button("gen_button", 10, 10, 100, 40, "Pay")}))
	writeIRFixture(t, goldenPath, docWithRoot([]ir.Node{button("gold_button", 10, 10, 100, 40, "Pay")}))

	out, err := Compile(Options{GeneratedPath: generatedPath, GoldenPath: goldenPath})
	if err != nil {
		t.Fatalf("Compile() error = %v", err)
	}
	if out.Source.GeneratedPath != generatedPath || out.Source.GoldenPath != goldenPath {
		t.Fatalf("expected source paths to be preserved: %#v", out.Source)
	}
	if err := WriteArtifacts(tmp, out); err != nil {
		t.Fatalf("WriteArtifacts() error = %v", err)
	}
	for _, name := range []string{"codia_structure_diff.v1.json", "codia_structure_diff_report.md"} {
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

func button(id string, x int, y int, width int, height int, label string) ir.Node {
	return ir.Node{
		ID:          id,
		Role:        ir.RoleButton,
		SourceBBox:  ir.BBox{X: x, Y: y, Width: width, Height: height},
		FigmaBBox:   ir.BBox{X: x, Y: y, Width: width, Height: height},
		FigmaType:   ir.FigmaFrame,
		VisibleName: "Button",
		SchemaID:    "Button_10_10_1",
		Children: []ir.Node{
			text(id+"_text", x+20, y+10, 40, 16, label),
			bgButton(id+"_bg", x, y, width, height),
		},
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
		Evidence:    []ir.Evidence{{Kind: "test_text"}},
	}
}

func bgButton(id string, x int, y int, width int, height int) ir.Node {
	return ir.Node{
		ID:          id,
		Role:        ir.RoleBgButton,
		SourceBBox:  ir.BBox{X: x, Y: y, Width: width, Height: height},
		FigmaBBox:   ir.BBox{X: x, Y: y, Width: width, Height: height},
		FigmaType:   ir.FigmaRoundedRectangle,
		VisibleName: "Background",
		SchemaID:    "bg_Button_10_10_1",
	}
}

func summarize(root ir.Node) ir.Summary {
	summary := ir.Summary{RoleCounts: map[string]int{}, FigmaTypeCounts: map[string]int{}}
	var walk func(ir.Node, int)
	walk = func(node ir.Node, depth int) {
		summary.NodeCount++
		if depth > summary.MaxDepth {
			summary.MaxDepth = depth
		}
		summary.RoleCounts[string(node.Role)]++
		summary.FigmaTypeCounts[string(node.FigmaType)]++
		for _, child := range node.Children {
			walk(child, depth+1)
		}
	}
	walk(root, 0)
	return summary
}

func writeIRFixture(t *testing.T, path string, doc ir.Document) {
	t.Helper()
	data, err := json.MarshalIndent(doc, "", "  ")
	if err != nil {
		t.Fatalf("marshal fixture: %v", err)
	}
	if err := os.WriteFile(path, data, 0o644); err != nil {
		t.Fatalf("write fixture: %v", err)
	}
}
