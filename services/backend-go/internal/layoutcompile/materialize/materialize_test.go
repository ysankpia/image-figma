package materialize

import (
	"testing"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/image/geometry"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/layoutir/contract"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/layoutir/validate"
)

func TestBuildMaterializesTextAndCompactImage(t *testing.T) {
	doc := Build(materializeTestDoc([]contract.Evidence{
		evidence("text_1", "text", geometry.Rect{X: 12, Y: 14, Width: 30, Height: 12}, map[string]string{"text": "Hello"}),
		evidence("image_1", "image", geometry.Rect{X: 60, Y: 20, Width: 32, Height: 30}, nil),
	}), Options{})

	text := findNode(doc.Root, contract.NodeText)
	if text == nil || text.Text == nil || text.Text.Characters != "Hello" {
		t.Fatalf("expected editable text leaf, got %+v", text)
	}
	image := findNode(doc.Root, contract.NodeImage)
	if image == nil || image.AssetRef == nil {
		t.Fatalf("expected image leaf with asset ref, got %+v", image)
	}
	if len(doc.Assets) != 1 || doc.Assets[0].ID != image.AssetRef.AssetID {
		t.Fatalf("asset mismatch: assets=%+v image=%+v", doc.Assets, image)
	}
	if report := validate.Document(doc); report.ErrorCount != 0 {
		t.Fatalf("validation errors = %+v", report.Findings)
	}
}

func TestBuildDemotesLargeTextBearingRasterToSubstrate(t *testing.T) {
	doc := Build(materializeTestDoc([]contract.Evidence{
		evidence("raster_1", "image", geometry.Rect{X: 0, Y: 0, Width: 180, Height: 120}, nil),
		evidence("text_1", "text", geometry.Rect{X: 20, Y: 20, Width: 40, Height: 12}, map[string]string{"text": "Title"}),
		evidence("text_2", "text", geometry.Rect{X: 20, Y: 50, Width: 70, Height: 12}, map[string]string{"text": "Subtitle"}),
	}), Options{})

	if image := findNode(doc.Root, contract.NodeImage); image != nil {
		t.Fatalf("large text-bearing raster should not become foreground image: %+v", image)
	}
	substrate := findNode(doc.Root, contract.NodeUnknownCrop)
	if substrate == nil || substrate.AssetRef == nil {
		t.Fatalf("large text-bearing raster should become fallback substrate crop, got %+v", substrate)
	}
	textCount := countNodes(doc.Root, contract.NodeText)
	if textCount != 2 {
		t.Fatalf("text leaves = %d, want 2", textCount)
	}
	if !hasDecision(doc.Decisions, contract.DecisionFallbackCrop, "materialize_text_bearing_raster_as_substrate") {
		t.Fatalf("expected fallback crop decision, got %+v", doc.Decisions)
	}
}

func TestBuildAddsTextEraserAboveSubstrateBelowText(t *testing.T) {
	doc := Build(materializeTestDoc([]contract.Evidence{
		evidence("raster_1", "image", geometry.Rect{X: 0, Y: 0, Width: 180, Height: 120}, nil),
		evidence("text_1", "text", geometry.Rect{X: 20, Y: 20, Width: 40, Height: 12}, map[string]string{"text": "Title"}),
		evidence("text_2", "text", geometry.Rect{X: 20, Y: 50, Width: 70, Height: 12}, map[string]string{"text": "Subtitle"}),
	}), Options{})

	erasers := findNodesByMeta(doc.Root, "zLayer", "text_eraser")
	if len(erasers) != 2 {
		t.Fatalf("text erasers = %d, want 2", len(erasers))
	}
	for _, eraser := range erasers {
		if eraser.Type != contract.NodeShape {
			t.Fatalf("eraser type = %s, want shape", eraser.Type)
		}
		if eraser.Style.Fill == "" {
			t.Fatalf("eraser should carry sampled fill: %+v", eraser)
		}
	}
	if !hasDecision(doc.Decisions, contract.DecisionEmit, "materialize_text_eraser_for_substrate") {
		t.Fatalf("expected text eraser decision, got %+v", doc.Decisions)
	}
}

func TestBuildSuppressesDecomposableLargeRaster(t *testing.T) {
	doc := Build(materializeTestDoc([]contract.Evidence{
		evidence("raster_1", "image", geometry.Rect{X: 0, Y: 0, Width: 200, Height: 130}, nil),
		evidence("text_1", "text", geometry.Rect{X: 10, Y: 10, Width: 40, Height: 12}, map[string]string{"text": "Title"}),
		evidence("text_2", "text", geometry.Rect{X: 85, Y: 35, Width: 32, Height: 12}, map[string]string{"text": "2"}),
		evidence("text_3", "text", geometry.Rect{X: 150, Y: 100, Width: 34, Height: 12}, map[string]string{"text": "Tab"}),
		evidence("shape_1", "shape", geometry.Rect{X: 4, Y: 70, Width: 192, Height: 34}, nil),
		evidence("shape_2", "shape", geometry.Rect{X: 150, Y: 28, Width: 34, Height: 26}, nil),
		evidence("icon_1", "icon", geometry.Rect{X: 12, Y: 98, Width: 20, Height: 20}, nil),
		evidence("icon_2", "icon", geometry.Rect{X: 168, Y: 32, Width: 12, Height: 12}, nil),
		evidence("image_1", "image", geometry.Rect{X: 64, Y: 76, Width: 36, Height: 28}, nil),
	}), Options{})

	if crop := findNode(doc.Root, contract.NodeUnknownCrop); crop != nil {
		t.Fatalf("decomposable raster should not become visible crop: %+v", crop)
	}
	if !hasDecision(doc.Decisions, contract.DecisionSuppress, "materialize_decomposable_raster_suppressed") {
		t.Fatalf("expected decomposable raster suppression, got %+v", doc.Decisions)
	}
	if countNodes(doc.Root, contract.NodeText) != 3 {
		t.Fatalf("internal text leaves should remain editable")
	}
}

func TestBuildKeepsSparseLargeRasterAsSubstrate(t *testing.T) {
	doc := Build(materializeTestDoc([]contract.Evidence{
		evidence("raster_1", "image", geometry.Rect{X: 0, Y: 0, Width: 180, Height: 120}, nil),
		evidence("text_1", "text", geometry.Rect{X: 20, Y: 20, Width: 40, Height: 12}, map[string]string{"text": "Title"}),
		evidence("text_2", "text", geometry.Rect{X: 20, Y: 50, Width: 70, Height: 12}, map[string]string{"text": "Subtitle"}),
	}), Options{})

	if crop := findNode(doc.Root, contract.NodeUnknownCrop); crop == nil {
		t.Fatalf("sparse text-bearing raster should remain fallback substrate")
	}
	if hasDecision(doc.Decisions, contract.DecisionSuppress, "materialize_decomposable_raster_suppressed") {
		t.Fatalf("sparse raster should not hit decomposable suppression: %+v", doc.Decisions)
	}
}

func TestBuildKeepsCompactMediaEvenWithInternalHints(t *testing.T) {
	doc := Build(materializeTestDoc([]contract.Evidence{
		evidence("image_1", "image", geometry.Rect{X: 20, Y: 20, Width: 55, Height: 45}, nil),
		evidence("text_1", "text", geometry.Rect{X: 28, Y: 28, Width: 18, Height: 10}, map[string]string{"text": "A"}),
		evidence("shape_1", "shape", geometry.Rect{X: 25, Y: 48, Width: 24, Height: 8}, nil),
		evidence("icon_1", "icon", geometry.Rect{X: 54, Y: 30, Width: 10, Height: 10}, nil),
	}), Options{})

	if image := findNode(doc.Root, contract.NodeImage); image == nil {
		t.Fatalf("compact media should remain image leaf")
	}
	if hasDecision(doc.Decisions, contract.DecisionSuppress, "materialize_decomposable_raster_suppressed") {
		t.Fatalf("compact media should not hit decomposable suppression: %+v", doc.Decisions)
	}
}

func TestBuildTreatsDetectorControlsAsHintsOnly(t *testing.T) {
	doc := Build(materializeTestDoc([]contract.Evidence{
		{
			ID:         "vision_button_1",
			Kind:       "vision_candidate",
			RoleHint:   "Button",
			BBox:       geometry.Rect{X: 20, Y: 20, Width: 80, Height: 30},
			Source:     "vision",
			Confidence: 0.80,
			SourceRefs: []contract.SourceRef{{Kind: "vision_detector_candidate", ID: "button_1"}},
		},
	}), Options{})

	if got := countNodes(doc.Root, contract.NodeGroup) + countNodes(doc.Root, contract.NodeShape) + countNodes(doc.Root, contract.NodeImage); got != 0 {
		t.Fatalf("detector control hint should not create visible/control node, got %d", got)
	}
	if !hasDecision(doc.Decisions, contract.DecisionSuppress, "materialize_semantic_hint_only") {
		t.Fatalf("expected hint-only suppression, got %+v", doc.Decisions)
	}
}

func materializeTestDoc(evidenceItems []contract.Evidence) contract.Document {
	root := contract.Node{
		ID:             "node_0001",
		Type:           contract.NodePage,
		BBox:           geometry.Rect{Width: 200, Height: 160},
		Layout:         contract.Layout{Mode: contract.LayoutColumn},
		SourceRefs:     []contract.SourceRef{{Kind: "source_image", ID: "source_image"}},
		Confidence:     1,
		FallbackPolicy: "none",
		Children: []contract.Node{{
			ID:             "section_0001",
			Type:           contract.NodeSection,
			BBox:           geometry.Rect{Width: 200, Height: 160},
			Layout:         contract.Layout{Mode: contract.LayoutAbsolute},
			SourceRefs:     []contract.SourceRef{{Kind: "layout_evidence", ID: "section_source"}},
			Confidence:     1,
			FallbackPolicy: "absolute_group_until_child_materialization",
		}},
	}
	return contract.Document{
		Version:     contract.Version,
		SourceImage: contract.ImageMeta{Width: 200, Height: 160},
		Root:        root,
		Evidence:    evidenceItems,
		Decisions: []contract.Decision{{
			ID:         "decision_0001",
			State:      contract.DecisionEmit,
			NodeID:     root.ID,
			Reason:     "source_image_page_initialized",
			SourceRefs: []contract.SourceRef{{Kind: "source_image", ID: "source_image"}},
			Score:      1,
		}},
	}
}

func evidence(id string, role string, box geometry.Rect, meta map[string]string) contract.Evidence {
	return contract.Evidence{
		ID:         id,
		Kind:       "m29_token",
		RoleHint:   role,
		BBox:       box,
		Source:     "m29",
		Confidence: 0.9,
		SourceRefs: []contract.SourceRef{{Kind: "m29_token", ID: id}},
		Meta:       meta,
	}
}

func findNode(root contract.Node, nodeType contract.NodeType) *contract.Node {
	if root.Type == nodeType {
		return &root
	}
	for _, child := range root.Children {
		if node := findNode(child, nodeType); node != nil {
			return node
		}
	}
	return nil
}

func countNodes(root contract.Node, nodeType contract.NodeType) int {
	count := 0
	if root.Type == nodeType {
		count++
	}
	for _, child := range root.Children {
		count += countNodes(child, nodeType)
	}
	return count
}

func findNodesByMeta(root contract.Node, key string, value string) []contract.Node {
	var out []contract.Node
	if root.Meta[key] == value {
		out = append(out, root)
	}
	for _, child := range root.Children {
		out = append(out, findNodesByMeta(child, key, value)...)
	}
	return out
}

func hasDecision(decisions []contract.Decision, state contract.DecisionState, reason string) bool {
	for _, decision := range decisions {
		if decision.State == state && decision.Reason == reason {
			return true
		}
	}
	return false
}
