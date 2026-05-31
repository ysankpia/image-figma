package advisor

import (
	"testing"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/image/geometry"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/layoutir/contract"
)

func TestBuildInputPreservesEvidenceFacts(t *testing.T) {
	doc := advisorDoc()
	input := BuildInput(doc)
	if input.Version != InputVersion {
		t.Fatalf("version = %q, want %q", input.Version, InputVersion)
	}
	if len(input.Evidence) != 2 {
		t.Fatalf("evidence = %d, want 2", len(input.Evidence))
	}
	text := input.Evidence[0]
	if text.ID != "ev_text" || text.Text != "Hello" || text.BBox.X != 10 {
		t.Fatalf("text evidence not preserved: %+v", text)
	}
	if len(input.Rows) != 1 {
		t.Fatalf("rows = %d, want 1", len(input.Rows))
	}
	row := input.Rows[0]
	if row.ID != "row_1" || row.FlowCount != 2 || row.RequiredWidth != 90 {
		t.Fatalf("unexpected row diagnostic: %+v", row)
	}
}

func advisorDoc() contract.Document {
	return contract.Document{
		Version:     contract.Version,
		SourceImage: contract.ImageMeta{Width: 200, Height: 120},
		Evidence: []contract.Evidence{
			{
				ID:         "ev_text",
				Kind:       "ocr_text",
				RoleHint:   "text",
				BBox:       geometry.Rect{X: 10, Y: 20, Width: 40, Height: 20},
				Meta:       map[string]string{"text": "Hello"},
				SourceRefs: []contract.SourceRef{{Kind: "ocr", ID: "ocr_1"}},
			},
			{
				ID:         "ev_icon",
				Kind:       "m29_token",
				RoleHint:   "icon",
				BBox:       geometry.Rect{X: 70, Y: 20, Width: 20, Height: 20},
				SourceRefs: []contract.SourceRef{{Kind: "m29_token", ID: "ev_icon"}},
			},
		},
		Root: contract.Node{
			ID:     "page",
			Type:   contract.NodePage,
			BBox:   geometry.Rect{Width: 200, Height: 120},
			Layout: contract.Layout{Mode: contract.LayoutColumn},
			Children: []contract.Node{
				{
					ID:     "row_1",
					Type:   contract.NodeRow,
					BBox:   geometry.Rect{X: 10, Y: 20, Width: 80, Height: 20},
					Layout: contract.Layout{Mode: contract.LayoutRow, Gap: 30},
					Meta:   map[string]string{"gapVariance": "0"},
					Children: []contract.Node{
						{
							ID:         "leaf_text",
							Type:       contract.NodeText,
							BBox:       geometry.Rect{X: 10, Y: 20, Width: 40, Height: 20},
							Layout:     contract.Layout{Mode: contract.LayoutAbsolute},
							SourceRefs: []contract.SourceRef{{Kind: "layout_evidence", ID: "ev_text"}},
							Text:       &contract.Text{Characters: "Hello"},
						},
						{
							ID:         "leaf_icon",
							Type:       contract.NodeIcon,
							BBox:       geometry.Rect{X: 70, Y: 20, Width: 20, Height: 20},
							Layout:     contract.Layout{Mode: contract.LayoutAbsolute},
							SourceRefs: []contract.SourceRef{{Kind: "layout_evidence", ID: "ev_icon"}},
						},
					},
				},
			},
		},
	}
}
