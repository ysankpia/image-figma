package segment

import (
	"testing"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/image/geometry"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/layoutir/contract"
)

func TestBuildSplitsTopLevelVerticalSections(t *testing.T) {
	result := Build(geometry.Rect{Width: 300, Height: 600}, []contract.Evidence{
		item("a", "text", 20, 20, 80, 20),
		item("b", "image", 20, 60, 100, 60),
		item("c", "text", 20, 260, 80, 20),
		item("d", "shape", 20, 310, 120, 40),
	}, Options{MinSectionEvidence: 1})
	if len(result.Sections) != 2 {
		t.Fatalf("sections = %d, want 2: %+v", len(result.Sections), result.Sections)
	}
	if result.Sections[0].BBox.Y != 20 || result.Sections[1].BBox.Y != 260 {
		t.Fatalf("unexpected section bboxes: %+v", result.Sections)
	}
	if len(result.Decisions) != 2 {
		t.Fatalf("decisions = %d, want 2", len(result.Decisions))
	}
}

func TestBuildMergesSmallTrailingCluster(t *testing.T) {
	result := Build(geometry.Rect{Width: 300, Height: 600}, []contract.Evidence{
		item("a", "text", 20, 20, 80, 20),
		item("b", "image", 20, 60, 100, 60),
		item("c", "text", 20, 260, 80, 20),
	}, Options{})
	if len(result.Sections) != 1 {
		t.Fatalf("sections = %d, want 1 after small trailing merge", len(result.Sections))
	}
}

func TestBuildIgnoresTextureFragmentEvidence(t *testing.T) {
	result := Build(geometry.Rect{Width: 300, Height: 600}, []contract.Evidence{
		item("a", "text", 20, 20, 80, 20),
		item("b", "texture_fragment", 20, 260, 80, 20),
	}, Options{MinSectionEvidence: 1})
	if len(result.Sections) != 1 {
		t.Fatalf("sections = %d, want 1", len(result.Sections))
	}
	if result.Sections[0].BBox.Y != 20 {
		t.Fatalf("texture fragment should not define section bbox: %+v", result.Sections[0].BBox)
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
