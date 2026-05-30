package emitter

import (
	"testing"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/ir"
)

func TestEmitBuildsFigmaLikeTreeWithRelativeBBox(t *testing.T) {
	doc := ir.Document{
		SchemaName: ir.SchemaName,
		Version:    ir.Version,
		Source:     ir.Source{InputPath: "sample", RootPath: "/0"},
		Summary:    ir.Summary{NodeCount: 2, MaxDepth: 1, RoleCounts: map[string]int{"root": 1, "TextView": 1}, FigmaTypeCounts: map[string]int{"FRAME": 1, "TEXT": 1}},
		Root: ir.Node{
			ID:          "root_0",
			Role:        ir.RoleRoot,
			FigmaType:   ir.FigmaFrame,
			VisibleName: "Root",
			SchemaID:    "root_0",
			FigmaBBox:   ir.BBox{X: 0, Y: 0, Width: 100, Height: 100},
			Children: []ir.Node{
				{
					ID:          "TextView_10_20_1",
					Role:        ir.RoleTextView,
					FigmaType:   ir.FigmaText,
					VisibleName: "Hello",
					SchemaID:    "TextView_10_20_1",
					Seq:         1,
					SourceBBox:  ir.BBox{X: 10, Y: 20, Width: 40, Height: 12},
					FigmaBBox:   ir.BBox{X: 14, Y: 20, Width: 40, Height: 12},
					Text:        &ir.Text{Characters: "Hello"},
				},
			},
		},
	}
	emitted, err := Emit(doc)
	if err != nil {
		t.Fatalf("Emit() error = %v", err)
	}
	if emitted.SchemaName != SchemaName || emitted.Root.Name != "Root" || len(emitted.Root.Children) != 1 {
		t.Fatalf("unexpected emitted tree: %#v", emitted)
	}
	child := emitted.Root.Children[0]
	if child.RelativeBBox.X != 14 || child.RelativeBBox.Y != 20 || child.SourceBBox.X != 10 || child.FigmaBBox.X != 14 {
		t.Fatalf("expected relative and dual bbox preserved, got %#v", child)
	}
}

func TestEmitRejectsInvalidVisibleNameForRole(t *testing.T) {
	doc := ir.Document{
		SchemaName: ir.SchemaName,
		Version:    ir.Version,
		Root: ir.Node{
			ID:          "root_0",
			Role:        ir.RoleRoot,
			FigmaType:   ir.FigmaFrame,
			VisibleName: "Groups",
		},
	}
	if _, err := Emit(doc); err == nil {
		t.Fatalf("expected invalid root visible name to fail")
	}
}
