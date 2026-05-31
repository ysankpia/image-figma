package advisor

import (
	"testing"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/image/geometry"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/layoutir/contract"
)

func TestValidateAcceptsCredibleHorizontalRow(t *testing.T) {
	input := validationInput(
		ev("a", "text", 10, 10, 40, 20),
		ev("b", "icon", 58, 11, 16, 18),
	)
	result := Result{
		Version: ResultVersion,
		Groups: []Group{{
			ID:          "g1",
			Type:        "row",
			Direction:   "horizontal",
			EvidenceIDs: []string{"a", "b"},
			ExpectedGap: 8,
			Confidence:  0.8,
		}},
	}
	validation := Validate(input, result, ValidateOptions{})
	if len(validation.AcceptedGroups) != 1 || len(validation.RejectedGroups) != 0 {
		t.Fatalf("validation = %+v", validation)
	}
	if validation.AcceptedGroups[0].RequiredWidth != 64 {
		t.Fatalf("required width = %d, want 64", validation.AcceptedGroups[0].RequiredWidth)
	}
}

func TestValidateRejectsInvalidGroups(t *testing.T) {
	tests := []struct {
		name   string
		input  Input
		group  Group
		reason string
	}{
		{
			name:   "unknown evidence",
			input:  validationInput(ev("a", "text", 0, 0, 20, 10)),
			group:  group("g1", "a", "missing"),
			reason: "unknown_evidence_id:missing",
		},
		{
			name:   "low confidence",
			input:  validationInput(ev("a", "text", 0, 0, 20, 10), ev("b", "icon", 24, 0, 10, 10)),
			group:  Group{ID: "g1", Type: "row", Direction: "horizontal", EvidenceIDs: []string{"a", "b"}, Confidence: 0.3},
			reason: "confidence_below_threshold",
		},
		{
			name:   "non flow role",
			input:  validationInput(ev("a", "text", 0, 0, 20, 10), ev("b", "shape", 24, 0, 10, 10)),
			group:  group("g1", "a", "b"),
			reason: "non_flow_evidence_role:b",
		},
		{
			name:   "too wide",
			input:  validationInput(ev("a", "text", 0, 0, 80, 10), ev("b", "icon", 90, 0, 80, 10)),
			group:  Group{ID: "g1", Type: "row", Direction: "horizontal", EvidenceIDs: []string{"a", "b"}, ExpectedGap: 80, Confidence: 0.9},
			reason: "required_width_overflow",
		},
		{
			name:   "slightly wider than preview overflow gate",
			input:  validationInput(ev("a", "text", 0, 0, 60, 10), ev("b", "icon", 62, 0, 40, 10)),
			group:  Group{ID: "g1", Type: "row", Direction: "horizontal", EvidenceIDs: []string{"a", "b"}, ExpectedGap: 4, Confidence: 0.9},
			reason: "required_width_overflow",
		},
		{
			name:   "y spread high",
			input:  validationInput(ev("a", "text", 0, 0, 20, 10), ev("b", "icon", 24, 40, 10, 10)),
			group:  group("g1", "a", "b"),
			reason: "flow_y_spread_high",
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := Result{Version: ResultVersion, Groups: []Group{tt.group}}
			validation := Validate(tt.input, result, ValidateOptions{})
			if len(validation.AcceptedGroups) != 0 || len(validation.RejectedGroups) != 1 {
				t.Fatalf("validation = %+v", validation)
			}
			if got := validation.RejectedGroups[0].Reason; !hasPrefix(got, tt.reason) {
				t.Fatalf("reason = %q, want prefix %q", got, tt.reason)
			}
		})
	}
}

func TestValidateRejectsDuplicateOwnership(t *testing.T) {
	input := validationInput(
		ev("a", "text", 0, 0, 20, 10),
		ev("b", "icon", 24, 0, 10, 10),
		ev("c", "text", 40, 0, 20, 10),
	)
	result := Result{
		Version: ResultVersion,
		Groups: []Group{
			group("g1", "a", "b"),
			group("g2", "b", "c"),
		},
	}
	validation := Validate(input, result, ValidateOptions{})
	if len(validation.AcceptedGroups) != 1 || len(validation.RejectedGroups) != 1 {
		t.Fatalf("validation = %+v", validation)
	}
	if got := validation.RejectedGroups[0].Reason; !hasPrefix(got, "duplicate_evidence_ownership") {
		t.Fatalf("reason = %q", got)
	}
}

func TestApplyCreatesExperimentRowsWithoutMutatingBaseline(t *testing.T) {
	doc := advisorDoc()
	validation := Validation{
		Version: ValidationVersion,
		AcceptedGroups: []AcceptedGroup{{
			GroupID:     "g1",
			Type:        "row",
			Direction:   "horizontal",
			EvidenceIDs: []string{"ev_text", "ev_icon"},
			BBox:        geometry.Rect{X: 10, Y: 20, Width: 80, Height: 20},
			ExpectedGap: 8,
			Confidence:  0.8,
		}},
	}
	experiment := Apply(doc, validation)
	if doc.Root.Children[0].ID != "row_1" {
		t.Fatalf("baseline mutated: %+v", doc.Root.Children)
	}
	if len(experiment.Root.Children) != 1 {
		t.Fatalf("experiment children = %+v", experiment.Root.Children)
	}
	var advisorRows []contract.Node
	collectRows(experiment.Root, &advisorRows)
	if len(advisorRows) != 1 || advisorRows[0].ID != "advisor_row_0001" {
		t.Fatalf("advisor rows = %+v", advisorRows)
	}
	if len(advisorRows[0].Children) != 2 {
		t.Fatalf("advisor row children = %+v", advisorRows[0].Children)
	}
}

func validationInput(items ...EvidenceItem) Input {
	return Input{
		Version:  InputVersion,
		Evidence: items,
	}
}

func ev(id string, role string, x int, y int, width int, height int) EvidenceItem {
	return EvidenceItem{
		ID:       id,
		Kind:     "test",
		RoleHint: role,
		BBox:     geometry.Rect{X: x, Y: y, Width: width, Height: height},
	}
}

func group(id string, ids ...string) Group {
	return Group{
		ID:          id,
		Type:        "row",
		Direction:   "horizontal",
		EvidenceIDs: ids,
		ExpectedGap: 4,
		Confidence:  0.9,
	}
}

func hasPrefix(value string, prefix string) bool {
	return len(value) >= len(prefix) && value[:len(prefix)] == prefix
}

func collectRows(node contract.Node, rows *[]contract.Node) {
	if node.Type == contract.NodeRow {
		*rows = append(*rows, node)
	}
	for _, child := range node.Children {
		collectRows(child, rows)
	}
}
