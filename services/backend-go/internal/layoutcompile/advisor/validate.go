package advisor

import (
	"fmt"
	"sort"
	"strings"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/image/geometry"
)

func Validate(input Input, result Result, options ValidateOptions) Validation {
	options = defaultValidateOptions(options)
	validation := Validation{
		Version:       ValidationVersion,
		GeneratedAt:   timestamp(),
		InputVersion:  input.Version,
		ResultVersion: result.Version,
		Warnings:      append([]string(nil), result.Warnings...),
	}
	if strings.TrimSpace(result.Version) != ResultVersion {
		validation.RejectedGroups = append(validation.RejectedGroups, RejectedGroup{
			Reason: fmt.Sprintf("unsupported_result_version:%s", result.Version),
		})
		validation.Summary = summarizeValidation(validation)
		return validation
	}
	evidenceByID := map[string]EvidenceItem{}
	for _, item := range input.Evidence {
		evidenceByID[item.ID] = item
	}
	owned := map[string]string{}
	for index, group := range result.Groups {
		groupID := strings.TrimSpace(group.ID)
		if groupID == "" {
			groupID = fmt.Sprintf("advisor_group_%04d", index+1)
		}
		reject := func(reason string) {
			validation.RejectedGroups = append(validation.RejectedGroups, RejectedGroup{
				GroupID:     groupID,
				Type:        group.Type,
				Direction:   group.Direction,
				EvidenceIDs: append([]string(nil), group.EvidenceIDs...),
				Reason:      reason,
			})
		}
		if !acceptedKind(group) {
			reject("unsupported_group_type_or_direction")
			continue
		}
		if group.Confidence < options.MinConfidence {
			reject("confidence_below_threshold")
			continue
		}
		ids := normalizedIDs(group.EvidenceIDs)
		if len(ids) < 2 {
			reject("group_requires_at_least_two_evidence_ids")
			continue
		}
		items := make([]EvidenceItem, 0, len(ids))
		duplicate := ""
		missing := ""
		for _, id := range ids {
			item, ok := evidenceByID[id]
			if !ok {
				missing = id
				break
			}
			if !flowEvidence(item) {
				reject("non_flow_evidence_role:" + id)
				items = nil
				break
			}
			if previous := owned[id]; previous != "" {
				duplicate = fmt.Sprintf("%s already owned by %s", id, previous)
				break
			}
			items = append(items, item)
		}
		if items == nil {
			continue
		}
		if missing != "" {
			reject("unknown_evidence_id:" + missing)
			continue
		}
		if duplicate != "" {
			reject("duplicate_evidence_ownership:" + duplicate)
			continue
		}
		metrics := groupMetrics(items, group.ExpectedGap)
		if metrics.RequiredWidth <= 0 || metrics.BBox.Empty() {
			reject("empty_group_geometry")
			continue
		}
		if metrics.FitRatio > options.MaxFitRatio {
			reject(fmt.Sprintf("required_width_overflow:%.3f", metrics.FitRatio))
			continue
		}
		if metrics.MedianHeight > 0 && float64(metrics.YSpread) > float64(metrics.MedianHeight)*options.MaxYSpreadFactor {
			reject("flow_y_spread_high")
			continue
		}
		if metrics.MaxGap > options.MaxGap {
			reject(fmt.Sprintf("gap_too_large:%d", metrics.MaxGap))
			continue
		}
		if metrics.GapVariance > options.MaxGapVariance {
			reject(fmt.Sprintf("gap_variance_high:%d", metrics.GapVariance))
			continue
		}
		for _, id := range ids {
			owned[id] = groupID
		}
		validation.AcceptedGroups = append(validation.AcceptedGroups, AcceptedGroup{
			GroupID:       groupID,
			Type:          group.Type,
			Direction:     group.Direction,
			EvidenceIDs:   ids,
			BBox:          metrics.BBox,
			ExpectedGap:   max(0, group.ExpectedGap),
			RequiredWidth: metrics.RequiredWidth,
			FitRatio:      metrics.FitRatio,
			YSpread:       metrics.YSpread,
			MedianHeight:  metrics.MedianHeight,
			Confidence:    group.Confidence,
			Reason:        group.Reason,
		})
	}
	validation.Summary = summarizeValidation(validation)
	return validation
}

func flowEvidence(item EvidenceItem) bool {
	switch strings.ToLower(strings.TrimSpace(item.RoleHint)) {
	case "text", "textview", "icon", "image", "imageview":
		return true
	default:
		return false
	}
}

func acceptedKind(group Group) bool {
	return strings.EqualFold(strings.TrimSpace(group.Type), "row") &&
		strings.EqualFold(strings.TrimSpace(group.Direction), "horizontal")
}

func normalizedIDs(ids []string) []string {
	seen := map[string]bool{}
	out := make([]string, 0, len(ids))
	for _, id := range ids {
		value := strings.TrimSpace(id)
		if value == "" || seen[value] {
			continue
		}
		seen[value] = true
		out = append(out, value)
	}
	sort.Strings(out)
	return out
}

type metrics struct {
	BBox          geometry.Rect
	RequiredWidth int
	FitRatio      float64
	YSpread       int
	MedianHeight  int
	MaxGap        int
	GapVariance   int
}

func groupMetrics(items []EvidenceItem, expectedGap int) metrics {
	sort.SliceStable(items, func(i, j int) bool {
		a, b := items[i].BBox, items[j].BBox
		if a.X != b.X {
			return a.X < b.X
		}
		if a.Y != b.Y {
			return a.Y < b.Y
		}
		return items[i].ID < items[j].ID
	})
	box := unionBoxes(items)
	gap := max(0, expectedGap)
	required := 0
	heights := make([]int, 0, len(items))
	gaps := make([]int, 0, len(items)-1)
	minY, maxY := 0, 0
	for i, item := range items {
		required += item.BBox.Width
		if item.BBox.Height > 0 {
			heights = append(heights, item.BBox.Height)
		}
		if i == 0 {
			minY, maxY = item.BBox.Y, item.BBox.Y
		} else {
			if item.BBox.Y < minY {
				minY = item.BBox.Y
			}
			if item.BBox.Y > maxY {
				maxY = item.BBox.Y
			}
			actualGap := item.BBox.X - items[i-1].BBox.Right()
			if actualGap > 0 {
				gaps = append(gaps, actualGap)
			}
		}
	}
	if len(items) > 1 {
		required += gap * (len(items) - 1)
	}
	out := metrics{
		BBox:          box,
		RequiredWidth: required,
		YSpread:       maxY - minY,
		MedianHeight:  median(heights),
		MaxGap:        maxSlice(gaps),
		GapVariance:   variance(gaps),
	}
	if box.Width > 0 {
		out.FitRatio = float64(required) / float64(box.Width)
	}
	return out
}

func summarizeValidation(validation Validation) ValidationSummary {
	return ValidationSummary{
		AcceptedCount: len(validation.AcceptedGroups),
		RejectedCount: len(validation.RejectedGroups),
	}
}
