package detector

import (
	"encoding/json"
	"fmt"
	"math"
	"sort"
	"strings"
)

type rawElements struct {
	Elements []rawElement `json:"elements"`
}

type rawElement struct {
	Role       string          `json:"role"`
	Label      string          `json:"label"`
	RawLabel   string          `json:"rawLabel"`
	Confidence *float64        `json:"confidence"`
	Score      *float64        `json:"score"`
	BBox       json.RawMessage `json:"bbox"`
}

func parseCandidates(text string, pass preparedPass, startIndex int) ([]Candidate, error) {
	payload, err := extractJSONPayload(text)
	if err != nil {
		return nil, err
	}
	var raw rawElements
	if err := json.Unmarshal([]byte(payload), &raw); err != nil {
		return nil, fmt.Errorf("parse detector JSON: %w", err)
	}
	out := make([]Candidate, 0, len(raw.Elements))
	for i, item := range raw.Elements {
		role := Role(strings.TrimSpace(item.Role))
		if !allowedRole(role) || (len(pass.Spec.AllowedRoles) > 0 && !pass.Spec.AllowedRoles[role]) {
			continue
		}
		norm, err := parseNormalizedBBox(item.BBox)
		if err != nil {
			continue
		}
		norm = clampNormalized(norm)
		if norm.Width <= 0 || norm.Height <= 0 {
			continue
		}
		bbox := BBox{
			X:      pass.Spec.SourceBBox.X + norm.X*pass.Spec.SourceBBox.Width,
			Y:      pass.Spec.SourceBBox.Y + norm.Y*pass.Spec.SourceBBox.Height,
			Width:  norm.Width * pass.Spec.SourceBBox.Width,
			Height: norm.Height * pass.Spec.SourceBBox.Height,
		}
		bbox = roundBBox(bbox)
		if bbox.Width <= 0 || bbox.Height <= 0 {
			continue
		}
		confidence := 0.70
		if item.Confidence != nil {
			confidence = *item.Confidence
		} else if item.Score != nil {
			confidence = *item.Score
		}
		label := strings.TrimSpace(item.RawLabel)
		if label == "" {
			label = strings.TrimSpace(item.Label)
		}
		candidate := Candidate{
			ID:                   fmt.Sprintf("det_%06d", startIndex+len(out)+1),
			Role:                 role,
			RawLabel:             label,
			Confidence:           clampFloat(confidence, 0, 1),
			BBox:                 bbox,
			BBoxNormalizedInPass: &norm,
			Source: CandidateSource{
				Kind:             "vision_model",
				PassID:           pass.Spec.ID,
				ModelOutputIndex: i,
				Reason:           pass.Spec.PromptName,
			},
			Merge: MergeState{State: "report_only", Reason: "default before permission gate"},
		}
		out = append(out, candidate)
	}
	return out, nil
}

func extractJSONPayload(text string) (string, error) {
	text = strings.TrimSpace(text)
	if text == "" {
		return "", fmt.Errorf("empty detector response")
	}
	if strings.HasPrefix(text, "```") {
		lines := strings.Split(text, "\n")
		if len(lines) >= 3 {
			text = strings.Join(lines[1:len(lines)-1], "\n")
		}
		text = strings.TrimSpace(strings.TrimPrefix(text, "json"))
	}
	start := strings.Index(text, "{")
	end := strings.LastIndex(text, "}")
	if start < 0 || end < start {
		return "", fmt.Errorf("detector response does not contain JSON object")
	}
	return text[start : end+1], nil
}

func parseNormalizedBBox(raw json.RawMessage) (NormalizedBBox, error) {
	if len(raw) == 0 {
		return NormalizedBBox{}, fmt.Errorf("missing bbox")
	}
	var arr []float64
	if err := json.Unmarshal(raw, &arr); err == nil && len(arr) == 4 {
		x1, y1, x2, y2 := arr[0], arr[1], arr[2], arr[3]
		if x2 < x1 {
			x1, x2 = x2, x1
		}
		if y2 < y1 {
			y1, y2 = y2, y1
		}
		return NormalizedBBox{X: x1, Y: y1, Width: x2 - x1, Height: y2 - y1}, nil
	}
	var obj map[string]float64
	if err := json.Unmarshal(raw, &obj); err == nil {
		if _, ok := obj["width"]; ok {
			return NormalizedBBox{X: obj["x"], Y: obj["y"], Width: obj["width"], Height: obj["height"]}, nil
		}
		x1 := obj["x1"]
		y1 := obj["y1"]
		x2 := obj["x2"]
		y2 := obj["y2"]
		if x2 < x1 {
			x1, x2 = x2, x1
		}
		if y2 < y1 {
			y1, y2 = y2, y1
		}
		return NormalizedBBox{X: x1, Y: y1, Width: x2 - x1, Height: y2 - y1}, nil
	}
	return NormalizedBBox{}, fmt.Errorf("invalid bbox")
}

func clampNormalized(b NormalizedBBox) NormalizedBBox {
	x1 := clampFloat(b.X, 0, 1)
	y1 := clampFloat(b.Y, 0, 1)
	x2 := clampFloat(b.X+b.Width, 0, 1)
	y2 := clampFloat(b.Y+b.Height, 0, 1)
	return NormalizedBBox{X: x1, Y: y1, Width: x2 - x1, Height: y2 - y1}
}

func allowedRole(role Role) bool {
	switch role {
	case RoleImageView, RoleTextView, RoleBackground, RoleStatusBar, RoleActionBar, RoleBottomNavigation, RoleListView, RoleViewGroup, RoleButton, RoleEditText:
		return true
	default:
		return false
	}
}

func dedupeCandidates(items []Candidate) []Candidate {
	sort.SliceStable(items, func(i, j int) bool {
		if items[i].Role != items[j].Role {
			return items[i].Role < items[j].Role
		}
		if items[i].Confidence != items[j].Confidence {
			return items[i].Confidence > items[j].Confidence
		}
		return items[i].ID < items[j].ID
	})
	kept := []Candidate{}
	for _, item := range items {
		duplicate := false
		for _, existing := range kept {
			if existing.Role == item.Role && iou(existing.BBox, item.BBox) >= 0.75 {
				duplicate = true
				break
			}
		}
		if !duplicate {
			kept = append(kept, item)
		}
	}
	sort.SliceStable(kept, func(i, j int) bool {
		if kept[i].Source.PassID != kept[j].Source.PassID {
			return kept[i].Source.PassID < kept[j].Source.PassID
		}
		return kept[i].ID < kept[j].ID
	})
	for i := range kept {
		kept[i].ID = fmt.Sprintf("det_%06d", i+1)
	}
	return kept
}

func iou(a, b BBox) float64 {
	ax2 := a.X + a.Width
	ay2 := a.Y + a.Height
	bx2 := b.X + b.Width
	by2 := b.Y + b.Height
	x1 := math.Max(a.X, b.X)
	y1 := math.Max(a.Y, b.Y)
	x2 := math.Min(ax2, bx2)
	y2 := math.Min(ay2, by2)
	if x2 <= x1 || y2 <= y1 {
		return 0
	}
	inter := (x2 - x1) * (y2 - y1)
	union := a.Width*a.Height + b.Width*b.Height - inter
	if union <= 0 {
		return 0
	}
	return inter / union
}

func roundBBox(b BBox) BBox {
	return BBox{
		X:      math.Round(b.X*10) / 10,
		Y:      math.Round(b.Y*10) / 10,
		Width:  math.Round(b.Width*10) / 10,
		Height: math.Round(b.Height*10) / 10,
	}
}

func clampFloat(value, low, high float64) float64 {
	if value < low {
		return low
	}
	if value > high {
		return high
	}
	return value
}
