package exportdsl

import (
	"testing"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/draft/contract"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/image/geometry"
)

func TestExportNestsGroupedLayersWithLocalCoordinates(t *testing.T) {
	graph := contract.Document{
		Version: contract.Version,
		Image:   contract.ImageMeta{Width: 300, Height: 500},
		Layers: []contract.Layer{
			{
				ID:      "shape",
				Kind:    contract.LayerShape,
				BBox:    geometry.Rect{X: 20, Y: 40, Width: 120, Height: 80},
				Z:       10,
				Visible: true,
				GroupID: "group_0001",
				Shape:   &contract.Shape{Fill: "#FFFFFF"},
				Decision: contract.Decision{
					State:         contract.DecisionEmit,
					BBoxAuthority: contract.BBoxAuthorityM29,
					Reason:        "surface",
				},
			},
			{
				ID:      "text",
				Kind:    contract.LayerText,
				BBox:    geometry.Rect{X: 32, Y: 55, Width: 60, Height: 16},
				Z:       30,
				Visible: true,
				GroupID: "group_0001",
				Text:    &contract.Text{Characters: "Title"},
				Decision: contract.Decision{
					State:         contract.DecisionEmit,
					BBoxAuthority: contract.BBoxAuthorityOCR,
					Reason:        "ocr_text",
				},
			},
		},
		Groups: []contract.Group{{
			ID:            "group_0001",
			Kind:          "major_region",
			BBox:          geometry.Rect{X: 20, Y: 40, Width: 120, Height: 80},
			ChildLayerIDs: []string{"shape", "text"},
			Decision: contract.Decision{
				State:         contract.DecisionEmit,
				BBoxAuthority: contract.BBoxAuthorityDerived,
				Reason:        "major_region_contains_editable_layers",
			},
		}},
	}

	doc := Export("task_test", graph)
	if len(doc.Root.Children) != 1 {
		t.Fatalf("expected one group child, got %+v", doc.Root.Children)
	}
	group := doc.Root.Children[0]
	if group.Type != "group" || group.ID != "group_0001" {
		t.Fatalf("unexpected group node: %+v", group)
	}
	if len(group.Children) != 2 {
		t.Fatalf("expected two local children, got %+v", group.Children)
	}
	if group.Children[0].BBox.X != 0 || group.Children[0].BBox.Y != 0 {
		t.Fatalf("expected background local origin, got %+v", group.Children[0].BBox)
	}
	if group.Children[1].BBox.X != 12 || group.Children[1].BBox.Y != 15 {
		t.Fatalf("expected text local coordinates, got %+v", group.Children[1].BBox)
	}
}
