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
