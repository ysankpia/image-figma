package assembly

import (
	"testing"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/detector"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/ir"
)

func TestDetectorImageMergesM29Fragments(t *testing.T) {
	doc := leafDoc([]ir.Node{
		image("frag_a", 12, 12, 18, 18),
		image("frag_b", 36, 14, 20, 18),
		text("label", 100, 100, 40, 18, "Name"),
	})
	det := detectorDoc(detector.Candidate{
		ID:         "det_cover",
		Role:       detector.RoleImageView,
		Confidence: 0.91,
		BBox:       detector.BBox{X: 10, Y: 10, Width: 52, Height: 28},
		Source:     detector.CandidateSource{Kind: "vision_model", PassID: "imageview"},
	})

	result, err := Build(Options{Leaf: doc, Detector: &det})
	if err != nil {
		t.Fatalf("Build() error = %v", err)
	}
	owner := findRole(result.Document.Root.Children, ir.RoleImageView)
	if owner == nil {
		t.Fatalf("expected emitted detector ImageView, children=%#v", result.Document.Root.Children)
	}
	if owner.SourceBBox != (ir.BBox{X: 10, Y: 10, Width: 52, Height: 28}) {
		t.Fatalf("detector bbox should be authority, got %#v", owner.SourceBBox)
	}
	if len(findRecords(result, decisionConsume, "frag_a")) != 1 || len(findRecords(result, decisionConsume, "frag_b")) != 1 {
		t.Fatalf("expected both fragments consumed, records=%#v", result.SourceCandidates.Candidates)
	}
	if result.Diagnostics.ConsumedCount != 2 || result.Diagnostics.OutputNodeCount != 2 {
		t.Fatalf("unexpected diagnostics: %#v", result.Diagnostics)
	}
}

func TestM29SmallFragmentConsumedByLargerImageOwner(t *testing.T) {
	doc := leafDoc([]ir.Node{
		image("large", 10, 10, 160, 120),
		image("small", 40, 40, 18, 18),
	})

	result, err := Build(Options{Leaf: doc})
	if err != nil {
		t.Fatalf("Build() error = %v", err)
	}
	if len(result.Document.Root.Children) != 1 || result.Document.Root.Children[0].ID != "large" {
		t.Fatalf("expected only large owner emitted, got %#v", result.Document.Root.Children)
	}
	records := findRecords(result, decisionConsume, "small")
	if len(records) != 1 || records[0].OwnerID != "large" {
		t.Fatalf("expected small consumed by large, records=%#v", records)
	}
}

func TestOCRImageInternalTextConsumedAndPlainTextPreserved(t *testing.T) {
	doc := leafDoc([]ir.Node{
		image("cover", 20, 20, 180, 140),
		text("inside", 50, 60, 45, 18, "VIP"),
		text("outside", 240, 60, 60, 18, "Title"),
	})

	result, err := Build(Options{Leaf: doc})
	if err != nil {
		t.Fatalf("Build() error = %v", err)
	}
	if findID(result.Document.Root.Children, "inside") != nil {
		t.Fatalf("expected image-internal OCR text consumed, children=%#v", result.Document.Root.Children)
	}
	if findID(result.Document.Root.Children, "outside") == nil {
		t.Fatalf("expected ordinary OCR text preserved, children=%#v", result.Document.Root.Children)
	}
	if got := findRecords(result, decisionConsume, "inside"); len(got) != 1 || got[0].OwnerID != "cover" {
		t.Fatalf("expected inside text consumed by cover, got %#v", got)
	}
}

func TestBackgroundFragmentSuppressesButControlEligibleBackgroundStays(t *testing.T) {
	doc := leafDoc([]ir.Node{
		backgroundWithEvidence("tiny_bg", "solid_background", 10, 10, 6, 4),
		backgroundWithEvidence("button_bg", "control_surface_background", 30, 30, 120, 42),
		text("button_text", 52, 42, 60, 18, "Pay"),
	})

	result, err := Build(Options{Leaf: doc})
	if err != nil {
		t.Fatalf("Build() error = %v", err)
	}
	if findID(result.Document.Root.Children, "tiny_bg") != nil {
		t.Fatalf("tiny background should be suppressed, children=%#v", result.Document.Root.Children)
	}
	if findID(result.Document.Root.Children, "button_bg") == nil {
		t.Fatalf("control background should remain for control synthesis, children=%#v", result.Document.Root.Children)
	}
	if len(findRecords(result, decisionSuppress, "tiny_bg")) != 1 {
		t.Fatalf("expected suppress record, records=%#v", result.SourceCandidates.Candidates)
	}
}

func TestDetectorButtonCannotCreateButton(t *testing.T) {
	doc := leafDoc([]ir.Node{
		text("label", 25, 22, 40, 18, "Pay"),
	})
	det := detectorDoc(detector.Candidate{
		ID:         "det_button",
		Role:       detector.RoleButton,
		Confidence: 0.93,
		BBox:       detector.BBox{X: 10, Y: 10, Width: 120, Height: 42},
		Source:     detector.CandidateSource{Kind: "vision_model", PassID: "layout"},
	})

	result, err := Build(Options{Leaf: doc, Detector: &det})
	if err != nil {
		t.Fatalf("Build() error = %v", err)
	}
	if result.Document.Summary.RoleCounts[string(ir.RoleButton)] != 0 {
		t.Fatalf("detector Button must not emit Button, summary=%#v", result.Document.Summary.RoleCounts)
	}
	if len(findRecords(result, decisionHint, "det_button")) != 1 {
		t.Fatalf("expected detector Button hint record, records=%#v", result.SourceCandidates.Candidates)
	}
}

func leafDoc(children []ir.Node) ir.Document {
	root := ir.Node{
		ID:          "root_0",
		Role:        ir.RoleRoot,
		SourceBBox:  ir.BBox{X: 0, Y: 0, Width: 320, Height: 640},
		FigmaBBox:   ir.BBox{X: 0, Y: 0, Width: 320, Height: 640},
		FigmaType:   ir.FigmaFrame,
		VisibleName: "Root",
		SchemaID:    "root_0",
		Style:       ir.Style{Visible: true, Opacity: 1},
		Children:    children,
	}
	assignSequences(&root)
	return ir.Document{SchemaName: ir.SchemaName, Version: ir.Version, Root: root, Summary: summarize(root)}
}

func image(id string, x, y, w, h int) ir.Node {
	box := ir.BBox{X: x, Y: y, Width: w, Height: h}
	return ir.Node{
		ID:          id,
		Role:        ir.RoleImageView,
		SourceBBox:  box,
		FigmaBBox:   box,
		FigmaType:   ir.FigmaRoundedRectangle,
		VisibleName: "Image",
		Asset:       &ir.Asset{Kind: "crop", Hash: id},
		Evidence:    []ir.Evidence{{Kind: "image_or_icon_crop", BBox: box, Confidence: 0.7, SourceID: id}},
		Style:       ir.Style{Visible: true, Opacity: 1},
	}
}

func text(id string, x, y, w, h int, value string) ir.Node {
	box := ir.BBox{X: x, Y: y, Width: w, Height: h}
	return ir.Node{
		ID:          id,
		Role:        ir.RoleTextView,
		SourceBBox:  box,
		FigmaBBox:   box,
		FigmaType:   ir.FigmaText,
		VisibleName: value,
		Text:        &ir.Text{Characters: value},
		Evidence:    []ir.Evidence{{Kind: "ocr_text", BBox: box, Confidence: 0.9, SourceID: id}},
		Style:       ir.Style{Visible: true, Opacity: 1},
	}
}

func backgroundWithEvidence(id string, kind string, x, y, w, h int) ir.Node {
	box := ir.BBox{X: x, Y: y, Width: w, Height: h}
	return ir.Node{
		ID:          id,
		Role:        ir.RoleBackground,
		SourceBBox:  box,
		FigmaBBox:   box,
		FigmaType:   ir.FigmaRoundedRectangle,
		VisibleName: "Background",
		Evidence:    []ir.Evidence{{Kind: kind, BBox: box, Confidence: 0.7, SourceID: id}},
		Style:       ir.Style{Visible: true, Opacity: 1},
	}
}

func detectorDoc(candidates ...detector.Candidate) detector.Document {
	return detector.Document{Version: detector.CandidatesVersion, Candidates: candidates}
}

func findRole(nodes []ir.Node, role ir.Role) *ir.Node {
	for i := range nodes {
		if nodes[i].Role == role {
			return &nodes[i]
		}
	}
	return nil
}

func findID(nodes []ir.Node, id string) *ir.Node {
	for i := range nodes {
		if nodes[i].ID == id {
			return &nodes[i]
		}
	}
	return nil
}

func findRecords(result Result, decision string, id string) []CandidateRecord {
	out := []CandidateRecord{}
	for _, record := range result.SourceCandidates.Candidates {
		if record.Decision == decision && record.ID == id {
			out = append(out, record)
		}
	}
	return out
}
