package evidence

import (
	"testing"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/image/geometry"
	m29contract "github.com/luqing-studio/image-figma/services/backend-go/internal/m29/contract"
	m29evidence "github.com/luqing-studio/image-figma/services/backend-go/internal/m29/evidence"
	visiondetector "github.com/luqing-studio/image-figma/services/backend-go/internal/vision/detector"
)

func TestNormalizeKeepsM29TextAndVisionHintSeparate(t *testing.T) {
	items := Normalize(Input{
		Bounds: geometry.Rect{Width: 300, Height: 600},
		Tokens: m29evidence.Document{Tokens: []m29evidence.Token{
			{
				ID:                 "tok_text",
				TokenType:          "text_token",
				BBox:               m29contract.BBox{X: 10, Y: 20, Width: 80, Height: 24},
				Disposition:        "main",
				Content:            m29evidence.TokenContent{Text: "Pay"},
				SourcePrimitiveIDs: []string{"prim_text"},
			},
		}},
		Detector: &visiondetector.Document{Candidates: []visiondetector.Candidate{
			{
				ID:         "cand_button",
				Role:       visiondetector.RoleButton,
				Confidence: 0.82,
				BBox:       visiondetector.BBox{X: 8, Y: 18, Width: 120, Height: 36},
				Source:     visiondetector.CandidateSource{PassID: "layout"},
			},
		}},
	})
	if len(items) != 2 {
		t.Fatalf("len(items) = %d, want 2: %+v", len(items), items)
	}
	if items[0].Kind != "m29_token" || items[0].RoleHint != "text" {
		t.Fatalf("first item = %+v, want m29 text", items[0])
	}
	if items[1].Kind != "vision_candidate" || items[1].RoleHint != "Button" {
		t.Fatalf("second item = %+v, want vision Button hint", items[1])
	}
	if items[0].Meta["text"] != "Pay" {
		t.Fatalf("text meta missing: %+v", items[0].Meta)
	}
}

func TestNormalizeClampsOutOfBoundsVisionCandidate(t *testing.T) {
	items := Normalize(Input{
		Bounds: geometry.Rect{Width: 100, Height: 100},
		Detector: &visiondetector.Document{Candidates: []visiondetector.Candidate{
			{
				ID:         "cand",
				Role:       visiondetector.RoleImageView,
				Confidence: 0.9,
				BBox:       visiondetector.BBox{X: 80, Y: 70, Width: 80, Height: 60},
				Source:     visiondetector.CandidateSource{PassID: "imageview"},
			},
		}},
	})
	if len(items) != 1 {
		t.Fatalf("len(items) = %d, want 1", len(items))
	}
	box := items[0].BBox
	if box.X != 80 || box.Y != 70 || box.Width != 20 || box.Height != 30 {
		t.Fatalf("clamped bbox = %+v", box)
	}
}
