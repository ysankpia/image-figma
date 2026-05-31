package validate

import (
	"testing"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/image/geometry"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/layoutir/contract"
)

func TestDocumentAcceptsMinimalPage(t *testing.T) {
	doc := contract.Document{
		Version: contract.Version,
		SourceImage: contract.ImageMeta{
			Width:  320,
			Height: 640,
		},
		Root: contract.Node{
			ID:   "node_0001",
			Type: contract.NodePage,
			BBox: geometry.Rect{Width: 320, Height: 640},
			Layout: contract.Layout{
				Mode: contract.LayoutColumn,
			},
			SourceRefs: []contract.SourceRef{{Kind: "source_image", ID: "source_image"}},
		},
		Decisions: []contract.Decision{{
			ID:     "decision_0001",
			State:  contract.DecisionEmit,
			NodeID: "node_0001",
			Reason: "page_initialized",
		}},
	}
	report := Document(doc)
	if report.ErrorCount != 0 {
		t.Fatalf("expected no validation errors, got %+v", report.Findings)
	}
}

func TestDocumentRejectsNodeWithoutSourceRefs(t *testing.T) {
	doc := contract.Document{
		Version: contract.Version,
		SourceImage: contract.ImageMeta{
			Width:  320,
			Height: 640,
		},
		Root: contract.Node{
			ID:   "node_0001",
			Type: contract.NodePage,
			BBox: geometry.Rect{Width: 320, Height: 640},
			Layout: contract.Layout{
				Mode: contract.LayoutColumn,
			},
		},
	}
	report := Document(doc)
	if !hasFinding(report, "LAYOUT_IR_NODE_SOURCE_REFS_MISSING") {
		t.Fatalf("expected missing sourceRefs finding, got %+v", report.Findings)
	}
}

func TestDocumentRejectsImageNodeWithoutDeclaredAsset(t *testing.T) {
	doc := contract.Document{
		Version: contract.Version,
		SourceImage: contract.ImageMeta{
			Width:  320,
			Height: 640,
		},
		Root: contract.Node{
			ID:   "node_0001",
			Type: contract.NodePage,
			BBox: geometry.Rect{Width: 320, Height: 640},
			Layout: contract.Layout{
				Mode: contract.LayoutColumn,
			},
			SourceRefs: []contract.SourceRef{{Kind: "source_image", ID: "source_image"}},
			Children: []contract.Node{{
				ID:   "node_0002",
				Type: contract.NodeImage,
				BBox: geometry.Rect{X: 10, Y: 20, Width: 40, Height: 30},
				Layout: contract.Layout{
					Mode: contract.LayoutAbsolute,
				},
				SourceRefs: []contract.SourceRef{{Kind: "m29", ID: "m29_0001"}},
				AssetRef:   &contract.AssetRef{AssetID: "missing_asset"},
			}},
		},
	}
	report := Document(doc)
	if !hasFinding(report, "LAYOUT_IR_NODE_ASSET_NOT_FOUND") {
		t.Fatalf("expected missing asset finding, got %+v", report.Findings)
	}
}

func hasFinding(report Report, code string) bool {
	for _, finding := range report.Findings {
		if finding.Code == code {
			return true
		}
	}
	return false
}
