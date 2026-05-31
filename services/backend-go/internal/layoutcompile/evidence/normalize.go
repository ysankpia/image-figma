package evidence

import (
	"fmt"
	"math"
	"sort"
	"strings"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/image/geometry"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/layoutir/contract"
	m29contract "github.com/luqing-studio/image-figma/services/backend-go/internal/m29/contract"
	m29evidence "github.com/luqing-studio/image-figma/services/backend-go/internal/m29/evidence"
	visiondetector "github.com/luqing-studio/image-figma/services/backend-go/internal/vision/detector"
)

type Input struct {
	Bounds   geometry.Rect
	Tokens   m29evidence.Document
	Detector *visiondetector.Document
}

func Normalize(input Input) []contract.Evidence {
	var out []contract.Evidence
	for _, token := range sortedTokens(input.Tokens.Tokens) {
		box := geometry.Clamp(rectFromM29(token.BBox), input.Bounds)
		if box.Empty() {
			continue
		}
		out = append(out, contract.Evidence{
			ID:         "evidence_" + token.ID,
			Kind:       "m29_token",
			RoleHint:   roleHintForToken(token),
			BBox:       box,
			Source:     "m29",
			Confidence: confidenceForToken(token),
			SourceRefs: tokenSourceRefs(token),
			Meta:       tokenMeta(token),
		})
	}
	if input.Detector != nil {
		for _, candidate := range sortedCandidates(input.Detector.Candidates) {
			box := geometry.Clamp(rectFromVision(candidate.BBox), input.Bounds)
			if box.Empty() {
				continue
			}
			out = append(out, contract.Evidence{
				ID:         "evidence_" + candidate.ID,
				Kind:       "vision_candidate",
				RoleHint:   string(candidate.Role),
				BBox:       box,
				Source:     "vision",
				Confidence: candidate.Confidence,
				SourceRefs: []contract.SourceRef{{
					Kind: "vision_detector_candidate",
					ID:   candidate.ID,
					Role: "semantic_hint",
				}},
				Meta: candidateMeta(candidate),
			})
		}
	}
	return out
}

func sortedTokens(tokens []m29evidence.Token) []m29evidence.Token {
	out := append([]m29evidence.Token(nil), tokens...)
	sort.SliceStable(out, func(i, j int) bool {
		a, b := out[i].BBox, out[j].BBox
		if a.Y != b.Y {
			return a.Y < b.Y
		}
		if a.X != b.X {
			return a.X < b.X
		}
		return out[i].ID < out[j].ID
	})
	return out
}

func sortedCandidates(candidates []visiondetector.Candidate) []visiondetector.Candidate {
	out := append([]visiondetector.Candidate(nil), candidates...)
	sort.SliceStable(out, func(i, j int) bool {
		a, b := out[i].BBox, out[j].BBox
		if a.Y != b.Y {
			return a.Y < b.Y
		}
		if a.X != b.X {
			return a.X < b.X
		}
		return out[i].ID < out[j].ID
	})
	return out
}

func roleHintForToken(token m29evidence.Token) string {
	switch token.TokenType {
	case "text_token":
		return "text"
	case "surface_region_token", "layer_background_token":
		return "shape"
	case "line_token":
		return "line"
	case "raster_region_token":
		if token.CompileHints.CanBeIcon {
			return "icon"
		}
		return "image"
	case "symbol_cluster_token":
		return "icon"
	case "texture_fragment_token":
		return "texture_fragment"
	default:
		return strings.TrimSuffix(token.TokenType, "_token")
	}
}

func confidenceForToken(token m29evidence.Token) float64 {
	if token.CompileHints.Confidence > 0 {
		return token.CompileHints.Confidence
	}
	switch token.TokenType {
	case "text_token":
		return 0.95
	case "surface_region_token", "layer_background_token", "line_token":
		return 0.72
	case "raster_region_token", "symbol_cluster_token":
		return 0.70
	default:
		return 0.50
	}
}

func tokenSourceRefs(token m29evidence.Token) []contract.SourceRef {
	refs := []contract.SourceRef{{
		Kind: "m29_token",
		ID:   token.ID,
		Role: "bbox_authority",
	}}
	for _, id := range token.SourcePrimitiveIDs {
		refs = append(refs, contract.SourceRef{
			Kind: "m29_primitive",
			ID:   id,
			Role: "source_primitive",
		})
	}
	return refs
}

func tokenMeta(token m29evidence.Token) map[string]string {
	meta := map[string]string{
		"tokenType":   token.TokenType,
		"disposition": token.Disposition,
	}
	if token.Content.Text != "" {
		meta["text"] = token.Content.Text
	}
	if len(token.Reasons) > 0 {
		meta["reasons"] = strings.Join(token.Reasons, ",")
	}
	if len(token.CompileHints.Reasons) > 0 {
		meta["compileHintReasons"] = strings.Join(token.CompileHints.Reasons, ",")
	}
	return meta
}

func candidateMeta(candidate visiondetector.Candidate) map[string]string {
	meta := map[string]string{
		"role":       string(candidate.Role),
		"passId":     candidate.Source.PassID,
		"mergeState": candidate.Merge.State,
	}
	if candidate.RawLabel != "" {
		meta["rawLabel"] = candidate.RawLabel
	}
	if candidate.Source.Reason != "" {
		meta["reason"] = candidate.Source.Reason
	}
	return meta
}

func rectFromM29(box m29contract.BBox) geometry.Rect {
	return geometry.Rect{X: box.X, Y: box.Y, Width: box.Width, Height: box.Height}
}

func rectFromVision(box visiondetector.BBox) geometry.Rect {
	return geometry.Rect{
		X:      int(math.Round(box.X)),
		Y:      int(math.Round(box.Y)),
		Width:  int(math.Round(box.Width)),
		Height: int(math.Round(box.Height)),
	}
}

func CountByKind(items []contract.Evidence) map[string]int {
	out := map[string]int{}
	for _, item := range items {
		out[item.Kind]++
	}
	return out
}

func CountByRoleHint(items []contract.Evidence) map[string]int {
	out := map[string]int{}
	for _, item := range items {
		key := item.RoleHint
		if key == "" {
			key = "(none)"
		}
		out[key]++
	}
	return out
}

func SummaryLine(items []contract.Evidence) string {
	return fmt.Sprintf("%d evidence items", len(items))
}
