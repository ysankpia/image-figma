package cluster

import (
	"testing"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/image/geometry"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/layoutir/contract"
)

func TestBuildRowsGroupsAlignedAnchors(t *testing.T) {
	section := sectionNode(0, 0, 300, 220)
	withRows, decisions := BuildRows(section, []contract.Evidence{
		item("a", "text", 20, 20, 80, 20),
		item("b", "icon", 120, 22, 20, 18),
		item("c", "text", 20, 90, 90, 22),
		item("d", "icon", 130, 92, 24, 20),
	}, Options{})
	if len(withRows.Children) != 2 {
		t.Fatalf("rows = %d, want 2: %+v", len(withRows.Children), withRows.Children)
	}
	if len(decisions) != 2 {
		t.Fatalf("decisions = %d, want 2", len(decisions))
	}
	if withRows.Children[0].BBox.Y != 20 || withRows.Children[1].BBox.Y != 90 {
		t.Fatalf("unexpected row bboxes: %+v", withRows.Children)
	}
	for _, row := range withRows.Children {
		if row.Layout.Mode != contract.LayoutRow {
			t.Fatalf("row layout mode = %s, want row", row.Layout.Mode)
		}
		if row.Layout.Gap != 20 {
			t.Fatalf("row gap = %d, want 20 for row %+v", row.Layout.Gap, row)
		}
		if row.Layout.Align != "center" {
			t.Fatalf("row align = %q, want center", row.Layout.Align)
		}
	}
}

func TestBuildRowsAbsorbsOverlappingSubstrate(t *testing.T) {
	section := sectionNode(0, 0, 300, 180)
	withRows, _ := BuildRows(section, []contract.Evidence{
		item("label", "text", 40, 40, 90, 20),
		item("icon", "icon", 150, 42, 18, 18),
		item("background", "shape", 20, 30, 180, 50),
	}, Options{})
	if len(withRows.Children) != 1 {
		t.Fatalf("rows = %d, want 1", len(withRows.Children))
	}
	row := withRows.Children[0]
	if row.BBox.X != 20 || row.BBox.Y != 30 || row.BBox.Width != 180 || row.BBox.Height != 50 {
		t.Fatalf("row should absorb overlapping substrate, got %+v", row.BBox)
	}
	if row.Meta["evidenceCount"] != "3" {
		t.Fatalf("row evidence count = %q", row.Meta["evidenceCount"])
	}
	if row.Layout.Mode != contract.LayoutRow {
		t.Fatalf("row layout mode = %s, want row", row.Layout.Mode)
	}
	if row.Layout.Gap != 20 {
		t.Fatalf("row gap = %d, want 20", row.Layout.Gap)
	}
	if row.Layout.Padding.Left != 20 || row.Layout.Padding.Top != 10 {
		t.Fatalf("row padding should be inferred from layout children, got %+v", row.Layout.Padding)
	}
}

func TestBuildRowsKeepsSingleChildRowsAsDiagnosableStructure(t *testing.T) {
	section := sectionNode(0, 0, 300, 180)
	withRows, decisions := BuildRows(section, []contract.Evidence{
		item("label", "text", 40, 40, 90, 20),
	}, Options{})
	if len(withRows.Children) != 1 {
		t.Fatalf("rows = %d, want 1 diagnosable row", len(withRows.Children))
	}
	if withRows.Children[0].Layout.Mode != contract.LayoutRow {
		t.Fatalf("single evidence row mode = %s, want row for structural diagnostics", withRows.Children[0].Layout.Mode)
	}
	if len(decisions) != 1 {
		t.Fatalf("decisions = %d, want 1", len(decisions))
	}
}

func TestBuildRowsDoesNotMergeSparseRowsIntoFakeFlexRow(t *testing.T) {
	section := sectionNode(0, 0, 300, 180)
	withRows, decisions := BuildRows(section, []contract.Evidence{
		item("first", "text", 40, 40, 90, 20),
		item("second", "text", 44, 70, 100, 20),
	}, Options{})
	if len(withRows.Children) != 2 {
		t.Fatalf("rows = %d, want 2 separate rows: %+v", len(withRows.Children), withRows.Children)
	}
	for _, row := range withRows.Children {
		if row.Meta["evidenceCount"] != "1" {
			t.Fatalf("unaligned singleton rows should stay separate, got %+v", row)
		}
	}
	if len(decisions) != 2 {
		t.Fatalf("decisions = %d, want 2", len(decisions))
	}
}

func TestBuildRowsIgnoresTinyIconAnchors(t *testing.T) {
	section := sectionNode(0, 0, 300, 180)
	withRows, decisions := BuildRows(section, []contract.Evidence{
		item("speck_1", "icon", 40, 40, 2, 2),
		item("speck_2", "icon", 80, 41, 2, 2),
	}, Options{})
	if len(withRows.Children) != 0 {
		t.Fatalf("tiny icon fragments should not create flex rows: %+v", withRows.Children)
	}
	if len(decisions) != 0 {
		t.Fatalf("decisions = %d, want 0", len(decisions))
	}
}

func TestBuildRowsRejectsOversizedOverlayExpansion(t *testing.T) {
	section := sectionNode(0, 0, 500, 300)
	withRows, _ := BuildRows(section, []contract.Evidence{
		item("label", "text", 40, 40, 90, 20),
		item("icon", "icon", 150, 42, 18, 18),
		item("hero", "image", 0, 0, 500, 240),
	}, Options{})
	if len(withRows.Children) != 1 {
		t.Fatalf("rows = %d, want 1", len(withRows.Children))
	}
	row := withRows.Children[0]
	if row.BBox.Width > 140 || row.BBox.Height > 30 {
		t.Fatalf("oversized overlay should not inflate row bbox, got %+v", row.BBox)
	}
	if row.Meta["evidenceCount"] != "2" {
		t.Fatalf("oversized overlay should not be absorbed, evidenceCount=%q", row.Meta["evidenceCount"])
	}
}

func TestBuildRowsUsesSectionSourceRefsWhenPresent(t *testing.T) {
	section := sectionNode(0, 0, 400, 160)
	section.SourceRefs = []contract.SourceRef{
		{Kind: "layout_evidence", ID: "a", Role: "section_member"},
		{Kind: "layout_evidence", ID: "b", Role: "section_member"},
	}
	withRows, _ := BuildRows(section, []contract.Evidence{
		item("a", "text", 20, 20, 80, 20),
		item("b", "icon", 120, 22, 20, 18),
		item("c", "text", 20, 90, 80, 20),
		item("d", "icon", 120, 92, 20, 18),
	}, Options{})
	if len(withRows.Children) != 1 {
		t.Fatalf("rows = %d, want 1 from section source refs: %+v", len(withRows.Children), withRows.Children)
	}
	row := withRows.Children[0]
	if row.BBox.Y != 20 || row.BBox.Bottom() > 42 {
		t.Fatalf("row should use only referenced evidence, got bbox %+v", row.BBox)
	}
	if row.Meta["evidenceCount"] != "2" {
		t.Fatalf("row evidence count = %q, want 2", row.Meta["evidenceCount"])
	}
}

func TestBuildRowsReturnsSectionWhenNoAnchors(t *testing.T) {
	section := sectionNode(0, 0, 300, 180)
	withRows, decisions := BuildRows(section, []contract.Evidence{
		item("background", "shape", 20, 30, 180, 50),
	}, Options{})
	if len(withRows.Children) != 0 {
		t.Fatalf("expected no rows without anchors, got %+v", withRows.Children)
	}
	if len(decisions) != 0 {
		t.Fatalf("decisions = %d, want 0", len(decisions))
	}
}

func TestBuildRowsRejectsSubstrateOutsideSection(t *testing.T) {
	section := sectionNode(50, 200, 200, 80)
	withRows, _ := BuildRows(section, []contract.Evidence{
		item("label", "text", 80, 220, 90, 20),
		item("icon", "icon", 180, 222, 18, 18),
		item("large_image", "image", 20, 40, 260, 220),
	}, Options{})
	if len(withRows.Children) != 1 {
		t.Fatalf("rows = %d, want 1", len(withRows.Children))
	}
	row := withRows.Children[0]
	if row.BBox.Y < section.BBox.Y || row.BBox.Bottom() > section.BBox.Bottom() {
		t.Fatalf("row escaped section: row=%+v section=%+v", row.BBox, section.BBox)
	}
	if row.Meta["evidenceCount"] != "2" {
		t.Fatalf("outside substrate should not be absorbed, evidenceCount=%q", row.Meta["evidenceCount"])
	}
}

func sectionNode(x int, y int, width int, height int) contract.Node {
	return contract.Node{
		ID:   "section_0001",
		Type: contract.NodeSection,
		Name: "Section 0001",
		BBox: geometry.Rect{X: x, Y: y, Width: width, Height: height},
		Layout: contract.Layout{
			Mode: contract.LayoutAbsolute,
		},
		SourceRefs: []contract.SourceRef{{Kind: "layout_evidence", ID: "section_source"}},
	}
}

func item(id string, role string, x int, y int, width int, height int) contract.Evidence {
	return contract.Evidence{
		ID:         id,
		Kind:       "m29_token",
		RoleHint:   role,
		BBox:       geometry.Rect{X: x, Y: y, Width: width, Height: height},
		Source:     "m29",
		Confidence: 0.8,
		SourceRefs: []contract.SourceRef{{Kind: "m29_token", ID: id}},
	}
}
