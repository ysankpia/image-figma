package unifiedvision

import (
	"testing"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/image/geometry"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/layoutir/contract"
)

func TestBuildInputSplitsByComplexityAndKeepsLocalCoordinates(t *testing.T) {
	doc := contract.Document{
		Version:     contract.Version,
		SourceImage: contract.ImageMeta{Width: 300, Height: 300},
		Root: contract.Node{
			ID:     "root",
			Type:   contract.NodePage,
			BBox:   geometry.Rect{Width: 300, Height: 300},
			Layout: contract.Layout{Mode: contract.LayoutColumn},
			Children: []contract.Node{{
				ID:     "section_0001",
				Type:   contract.NodeSection,
				BBox:   geometry.Rect{X: 20, Y: 20, Width: 160, Height: 220},
				Layout: contract.Layout{Mode: contract.LayoutColumn},
				SourceRefs: []contract.SourceRef{
					{Kind: "layout_evidence", ID: "text_1"},
					{Kind: "layout_evidence", ID: "text_2"},
					{Kind: "layout_evidence", ID: "text_3"},
					{Kind: "layout_evidence", ID: "text_4"},
					{Kind: "layout_evidence", ID: "icon_1"},
					{Kind: "layout_evidence", ID: "shape_1"},
				},
			}},
		},
		Evidence: []contract.Evidence{
			{ID: "text_1", Kind: "m29", RoleHint: "text", BBox: geometry.Rect{X: 30, Y: 30, Width: 40, Height: 20}, Meta: map[string]string{"text": "A"}},
			{ID: "icon_1", Kind: "m29", RoleHint: "icon", BBox: geometry.Rect{X: 80, Y: 30, Width: 16, Height: 16}},
			{ID: "text_2", Kind: "m29", RoleHint: "text", BBox: geometry.Rect{X: 30, Y: 80, Width: 40, Height: 20}, Meta: map[string]string{"text": "B"}},
			{ID: "text_3", Kind: "m29", RoleHint: "text", BBox: geometry.Rect{X: 30, Y: 150, Width: 40, Height: 20}, Meta: map[string]string{"text": "C"}},
			{ID: "text_4", Kind: "m29", RoleHint: "text", BBox: geometry.Rect{X: 30, Y: 210, Width: 40, Height: 20}, Meta: map[string]string{"text": "D"}},
			{ID: "shape_1", Kind: "m29", RoleHint: "shape", BBox: geometry.Rect{X: 20, Y: 20, Width: 160, Height: 220}},
		},
	}
	input := BuildInput(doc, Options{MaxItemsPerBatch: 2, HardMaxItemsPerBatch: 3, MaxComplexity: 1, CropPadding: 5})
	if len(input.Batches) < 2 {
		t.Fatalf("expected split batches, got %+v", input.Batches)
	}
	for _, batch := range input.Batches {
		if len(batch.Evidence) > 3 {
			t.Fatalf("batch exceeds hard cap: %+v", batch)
		}
		for _, item := range batch.Evidence {
			if item.RoleHint == "shape" {
				t.Fatalf("shape evidence should not be sent to unified vision")
			}
			if item.BBoxLocal.X != item.BBox.X-batch.CropBBox.X || item.BBoxLocal.Y != item.BBox.Y-batch.CropBBox.Y {
				t.Fatalf("bad local bbox for %+v in crop %+v", item, batch.CropBBox)
			}
		}
	}
}
