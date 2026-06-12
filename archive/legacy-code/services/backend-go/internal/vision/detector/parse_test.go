package detector

import (
	"image"
	"testing"
)

func TestParseCandidatesRestoresOriginalBBox(t *testing.T) {
	spec, err := passSpec("bottom_nav", image.Pt(1000, 2000))
	if err != nil {
		t.Fatalf("pass spec: %v", err)
	}
	pass := preparedPass{Spec: spec}
	raw := "```json\n{\"elements\":[{\"role\":\"ImageView\",\"label\":\"tab icon\",\"confidence\":0.91,\"bbox\":[0.1,0.2,0.3,0.4]},{\"role\":\"Button\",\"label\":\"tab button\",\"bbox\":[0,0,0.1,0.1]},{\"role\":\"UnknownThing\",\"label\":\"ignored\",\"bbox\":[0,0,1,1]}]}\n```"
	items, err := parseCandidates(raw, pass, 0)
	if err != nil {
		t.Fatalf("parse: %v", err)
	}
	if len(items) != 2 {
		t.Fatalf("expected 2 known-role candidates, got %d", len(items))
	}
	item := items[0]
	if item.ID != "det_000001" || item.Role != RoleImageView || item.Source.PassID != "bottom_nav" {
		t.Fatalf("unexpected candidate identity: %+v", item)
	}
	if !item.Source.PreferredByPass {
		t.Fatalf("expected ImageView to be preferred by bottom_nav pass")
	}
	if item.BBox.X != 100 || item.BBox.Y != 1712 || item.BBox.Width != 200 || item.BBox.Height != 72 {
		t.Fatalf("bbox was not restored into source coordinates: %+v", item.BBox)
	}
	if item.Merge.State != "report_only" {
		t.Fatalf("expected report_only merge state, got %q", item.Merge.State)
	}
	button := items[1]
	if button.Role != RoleButton || button.Source.PreferredByPass {
		t.Fatalf("expected non-preferred Button evidence to be preserved: %+v", button)
	}
	if button.Merge.State != "report_only" || button.Merge.Reason == "" {
		t.Fatalf("expected report-only merge reason on preserved Button: %+v", button.Merge)
	}
}

func TestDedupeCandidatesKeepsHighestConfidence(t *testing.T) {
	items := []Candidate{
		{ID: "det_000001", Role: RoleImageView, Confidence: 0.60, BBox: BBox{X: 10, Y: 10, Width: 20, Height: 20}, Source: CandidateSource{PassID: "layout"}},
		{ID: "det_000002", Role: RoleImageView, Confidence: 0.95, BBox: BBox{X: 11, Y: 11, Width: 20, Height: 20}, Source: CandidateSource{PassID: "imageview"}},
		{ID: "det_000003", Role: RoleBackground, Confidence: 0.50, BBox: BBox{X: 11, Y: 11, Width: 20, Height: 20}, Source: CandidateSource{PassID: "background"}},
	}
	out := dedupeCandidates(items)
	if len(out) != 2 {
		t.Fatalf("expected 2 candidates after same-role dedupe, got %d", len(out))
	}
	foundImage := false
	for _, item := range out {
		if item.Role == RoleImageView {
			foundImage = true
			if item.Confidence != 0.95 {
				t.Fatalf("expected higher confidence ImageView to survive: %+v", item)
			}
		}
	}
	if !foundImage {
		t.Fatalf("expected surviving ImageView")
	}
}
