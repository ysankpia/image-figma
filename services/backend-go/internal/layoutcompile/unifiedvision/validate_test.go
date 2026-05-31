package unifiedvision

import (
	"testing"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/image/geometry"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/layoutir/contract"
)

func TestValidateAcceptsPhysicalHorizontalAndVerticalGroups(t *testing.T) {
	input := validationInput()
	result := Result{
		Version: ResultVersion,
		Batches: []BatchResult{{
			BatchID:   "uv_batch_0001",
			SectionID: "section_0001",
			Result: ModelResult{
				Version: ResultVersion,
				Groups: []Group{
					{ID: "row", Direction: "horizontal", Gap: 8, Members: []string{"text_1", "icon_1"}, Confidence: 0.95},
					{ID: "column", Direction: "vertical", Gap: 6, Members: []string{"text_2", "text_3"}, Confidence: 0.90},
				},
				ElementStyles: map[string]ElementStyle{
					"text_1": {FontSize: 16, FontWeight: 600, Color: "#111111"},
				},
			},
		}},
	}
	validation := Validate(input, result, Options{})
	if len(validation.AcceptedGroups) != 2 {
		t.Fatalf("accepted groups = %+v, rejected=%+v", validation.AcceptedGroups, validation.RejectedGroups)
	}
	if validation.Summary.Coverage != 1 {
		t.Fatalf("coverage = %.3f, want 1", validation.Summary.Coverage)
	}
	if len(validation.AcceptedStyles) != 1 {
		t.Fatalf("accepted styles = %+v", validation.AcceptedStyles)
	}
}

func TestValidateRejectsBadGroups(t *testing.T) {
	tests := []struct {
		name    string
		group   Group
		options Options
		reason  string
	}{
		{
			name:   "unknown id",
			group:  Group{ID: "g", Direction: "horizontal", Gap: 8, Members: []string{"text_1", "missing"}, Confidence: 0.9},
			reason: "unknown_evidence_id:missing",
		},
		{
			name:   "single member",
			group:  Group{ID: "g", Direction: "horizontal", Gap: 8, Members: []string{"text_1"}, Confidence: 0.9},
			reason: "group_requires_at_least_two_members",
		},
		{
			name:   "low confidence",
			group:  Group{ID: "g", Direction: "horizontal", Gap: 8, Members: []string{"text_1", "icon_1"}, Confidence: 0.2},
			reason: "confidence_below_threshold",
		},
		{
			name:   "overflow",
			group:  Group{ID: "g", Direction: "horizontal", Gap: 80, Members: []string{"text_1", "icon_1"}, Confidence: 0.9},
			reason: "required_size_overflow:2.125",
		},
		{
			name:    "bad spread",
			group:   Group{ID: "g", Direction: "horizontal", Gap: 8, Members: []string{"text_1", "text_3"}, Confidence: 0.9},
			options: Options{MaxFitRatio: 10},
			reason:  "cross_axis_spread_high",
		},
		{
			name:   "bad gap",
			group:  Group{ID: "g", Direction: "horizontal", Gap: 120, Members: []string{"text_1", "icon_1"}, Confidence: 0.9},
			reason: "gap_too_large:120",
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := Result{
				Version: ResultVersion,
				Batches: []BatchResult{{
					BatchID:   "uv_batch_0001",
					SectionID: "section_0001",
					Result:    ModelResult{Version: ResultVersion, Groups: []Group{tt.group}},
				}},
			}
			validation := Validate(validationInput(), result, tt.options)
			if len(validation.AcceptedGroups) != 0 || len(validation.RejectedGroups) != 1 {
				t.Fatalf("accepted=%+v rejected=%+v", validation.AcceptedGroups, validation.RejectedGroups)
			}
			if validation.RejectedGroups[0].Reason != tt.reason {
				t.Fatalf("reason = %q, want %q", validation.RejectedGroups[0].Reason, tt.reason)
			}
		})
	}
}

func TestValidateRejectsDuplicateOwnershipAndBadStyles(t *testing.T) {
	result := Result{
		Version: ResultVersion,
		Batches: []BatchResult{{
			BatchID:   "uv_batch_0001",
			SectionID: "section_0001",
			Result: ModelResult{
				Version: ResultVersion,
				Groups: []Group{
					{ID: "first", Direction: "horizontal", Gap: 8, Members: []string{"text_1", "icon_1"}, Confidence: 0.9},
					{ID: "second", Direction: "horizontal", Gap: 8, Members: []string{"text_1", "text_2"}, Confidence: 0.9},
				},
				ElementStyles: map[string]ElementStyle{
					"icon_1": {FontSize: 16, Color: "#111111"},
					"text_2": {FontSize: 100, Color: "#111111"},
					"text_3": {FontSize: 14, Color: "red"},
				},
			},
		}},
	}
	validation := Validate(validationInput(), result, Options{})
	if len(validation.AcceptedGroups) != 1 {
		t.Fatalf("accepted groups = %+v", validation.AcceptedGroups)
	}
	if len(validation.RejectedGroups) != 1 || validation.RejectedGroups[0].Reason != "duplicate_evidence_ownership:text_1_owned_by_first" {
		t.Fatalf("rejected groups = %+v", validation.RejectedGroups)
	}
	if len(validation.RejectedStyles) != 3 {
		t.Fatalf("rejected styles = %+v", validation.RejectedStyles)
	}
}

func validationInput() Input {
	batch := BatchInput{
		ID:          "uv_batch_0001",
		SectionID:   "section_0001",
		SectionBBox: geometry.Rect{X: 0, Y: 0, Width: 220, Height: 120},
		CropBBox:    geometry.Rect{X: 0, Y: 0, Width: 220, Height: 120},
		Evidence: []EvidenceItem{
			{ID: "text_1", Kind: "m29", RoleHint: "text", BBox: geometry.Rect{X: 10, Y: 10, Width: 40, Height: 20}, Text: "A"},
			{ID: "icon_1", Kind: "m29", RoleHint: "icon", BBox: geometry.Rect{X: 58, Y: 12, Width: 16, Height: 16}},
			{ID: "text_2", Kind: "m29", RoleHint: "text", BBox: geometry.Rect{X: 10, Y: 48, Width: 40, Height: 20}, Text: "B"},
			{ID: "text_3", Kind: "m29", RoleHint: "text", BBox: geometry.Rect{X: 10, Y: 74, Width: 40, Height: 20}, Text: "C"},
		},
	}
	return Input{
		Version:     InputVersion,
		SourceImage: contract.ImageMeta{Width: 220, Height: 120},
		Batches:     []BatchInput{batch},
	}
}
