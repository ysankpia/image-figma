package unifiedvision

import (
	"fmt"
	"sort"
	"strings"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/image/geometry"
)

func Validate(input Input, result Result, options Options) Validation {
	options = options.withDefaults()
	validation := Validation{
		Version:        ValidationVersion,
		GeneratedAt:    timestamp(),
		InputVersion:   input.Version,
		ResultVersion:  result.Version,
		AcceptedStyles: map[string]ElementStyle{},
	}
	batches := map[string]BatchInput{}
	totalEvidence := map[string]bool{}
	for _, batch := range input.Batches {
		batches[batch.ID] = batch
		for _, item := range batch.Evidence {
			totalEvidence[item.ID] = true
		}
	}
	if strings.TrimSpace(result.Version) != ResultVersion {
		validation.RejectedGroups = append(validation.RejectedGroups, RejectedGroup{Reason: "unsupported_result_version:" + result.Version})
		validation.Summary = summarizeValidation(validation, totalEvidence)
		return validation
	}
	owned := map[string]string{}
	duplicateOwnership := 0
	for _, batchResult := range result.Batches {
		batch, ok := batches[batchResult.BatchID]
		batchValidation := BatchValidation{
			BatchID:         batchResult.BatchID,
			SectionID:       batchResult.SectionID,
			Fallback:        batchResult.Error != "",
			Reason:          batchResult.Error,
			RepairAttempted: batchResult.RepairAttempt,
		}
		if !ok {
			batchValidation.Fallback = true
			batchValidation.Reason = "unknown_batch_id"
			validation.Batches = append(validation.Batches, batchValidation)
			continue
		}
		if batchResult.Error != "" {
			validation.Batches = append(validation.Batches, batchValidation)
			continue
		}
		evidenceByID := map[string]EvidenceItem{}
		for _, item := range batch.Evidence {
			evidenceByID[item.ID] = item
		}
		for index, group := range batchResult.Result.Groups {
			accepted, rejected := validateGroup(batch, evidenceByID, owned, groupID(batch.ID, index, group.ID), group, options)
			if rejected != nil {
				if strings.HasPrefix(rejected.Reason, "duplicate_evidence_ownership:") {
					duplicateOwnership++
				}
				validation.RejectedGroups = append(validation.RejectedGroups, *rejected)
				batchValidation.RejectedCount++
				continue
			}
			for _, id := range accepted.EvidenceIDs {
				owned[id] = accepted.GroupID
			}
			validation.AcceptedGroups = append(validation.AcceptedGroups, accepted)
			batchValidation.AcceptedCount++
		}
		for id, style := range batchResult.Result.ElementStyles {
			if reject := validateStyle(batch.ID, evidenceByID, id, style); reject != nil {
				validation.RejectedStyles = append(validation.RejectedStyles, *reject)
				continue
			}
			validation.AcceptedStyles[id] = style
		}
		if batchValidation.RejectedCount > 0 {
			batchValidation.Reason = batchRejectSummary(validation.RejectedGroups, batch.ID)
		}
		validation.Batches = append(validation.Batches, batchValidation)
	}
	for _, batch := range input.Batches {
		if !batchValidated(validation.Batches, batch.ID) {
			validation.Batches = append(validation.Batches, BatchValidation{
				BatchID:   batch.ID,
				SectionID: batch.SectionID,
				Fallback:  true,
				Reason:    "missing_model_result",
			})
		}
	}
	validation.Summary = summarizeValidation(validation, totalEvidence)
	validation.Summary.DuplicateOwnershipCount = duplicateOwnership
	return validation
}

func validateGroup(batch BatchInput, evidenceByID map[string]EvidenceItem, owned map[string]string, id string, group Group, options Options) (AcceptedGroup, *RejectedGroup) {
	reject := func(reason string) (AcceptedGroup, *RejectedGroup) {
		return AcceptedGroup{}, &RejectedGroup{
			BatchID:     batch.ID,
			GroupID:     id,
			Name:        group.Name,
			Direction:   group.Direction,
			EvidenceIDs: append([]string(nil), group.Members...),
			Reason:      reason,
		}
	}
	direction := strings.ToLower(strings.TrimSpace(group.Direction))
	if direction != "horizontal" && direction != "vertical" {
		return reject("unsupported_direction")
	}
	if group.Confidence < options.MinConfidence {
		return reject("confidence_below_threshold")
	}
	if group.Gap < 0 {
		return reject("negative_gap")
	}
	if group.Gap > options.MaxGap {
		return reject(fmt.Sprintf("gap_too_large:%d", group.Gap))
	}
	ids := normalizedIDs(group.Members)
	if len(ids) != len(group.Members) {
		return reject("duplicate_member_id")
	}
	if len(ids) < 2 {
		return reject("group_requires_at_least_two_members")
	}
	items := make([]EvidenceItem, 0, len(ids))
	for _, memberID := range ids {
		item, ok := evidenceByID[memberID]
		if !ok {
			return reject("unknown_evidence_id:" + memberID)
		}
		if !flowRole(item.RoleHint) {
			return reject("non_flow_evidence:" + memberID)
		}
		if previous := owned[memberID]; previous != "" {
			return reject("duplicate_evidence_ownership:" + memberID + "_owned_by_" + previous)
		}
		items = append(items, item)
	}
	metrics := groupMetrics(items, direction, group.Gap)
	if metrics.FitRatio > options.MaxFitRatio {
		return reject(fmt.Sprintf("required_size_overflow:%.3f", metrics.FitRatio))
	}
	if metrics.MedianCross > 0 && float64(metrics.CrossSpread) > float64(metrics.MedianCross)*options.MaxYSpreadFactor {
		return reject("cross_axis_spread_high")
	}
	if metrics.MaxGap > options.MaxGap {
		return reject(fmt.Sprintf("actual_gap_too_large:%d", metrics.MaxGap))
	}
	if metrics.GapVariance > options.MaxGapVariance {
		return reject(fmt.Sprintf("gap_variance_high:%d", metrics.GapVariance))
	}
	return AcceptedGroup{
		GroupID:      id,
		Name:         group.Name,
		Direction:    direction,
		BatchID:      batch.ID,
		SectionID:    batch.SectionID,
		EvidenceIDs:  ids,
		BBox:         metrics.BBox,
		Gap:          group.Gap,
		RequiredSize: metrics.RequiredSize,
		FitRatio:     metrics.FitRatio,
		CrossSpread:  metrics.CrossSpread,
		MedianCross:  metrics.MedianCross,
		MaxGap:       metrics.MaxGap,
		GapVariance:  metrics.GapVariance,
		Confidence:   group.Confidence,
		Reason:       group.Reason,
	}, nil
}

type validationMetrics struct {
	BBox         geometry.Rect
	RequiredSize int
	FitRatio     float64
	CrossSpread  int
	MedianCross  int
	MaxGap       int
	GapVariance  int
}

func groupMetrics(items []EvidenceItem, direction string, expectedGap int) validationMetrics {
	copied := append([]EvidenceItem(nil), items...)
	if direction == "vertical" {
		sort.SliceStable(copied, func(i, j int) bool {
			if copied[i].BBox.Y != copied[j].BBox.Y {
				return copied[i].BBox.Y < copied[j].BBox.Y
			}
			return copied[i].ID < copied[j].ID
		})
	} else {
		sort.SliceStable(copied, func(i, j int) bool {
			if copied[i].BBox.X != copied[j].BBox.X {
				return copied[i].BBox.X < copied[j].BBox.X
			}
			return copied[i].ID < copied[j].ID
		})
	}
	box := unionEvidence(copied)
	required := maxInt(0, expectedGap) * maxInt(0, len(copied)-1)
	crossValues := make([]int, 0, len(copied))
	gaps := make([]int, 0, len(copied)-1)
	minCross, maxCross := 0, 0
	for i, item := range copied {
		if direction == "vertical" {
			required += item.BBox.Height
			crossValues = append(crossValues, item.BBox.Width)
			if i == 0 {
				minCross, maxCross = item.BBox.X, item.BBox.X
			} else {
				if item.BBox.X < minCross {
					minCross = item.BBox.X
				}
				if item.BBox.X > maxCross {
					maxCross = item.BBox.X
				}
				gap := item.BBox.Y - copied[i-1].BBox.Bottom()
				if gap > 0 {
					gaps = append(gaps, gap)
				}
			}
			continue
		}
		required += item.BBox.Width
		crossValues = append(crossValues, item.BBox.Height)
		if i == 0 {
			minCross, maxCross = item.BBox.Y, item.BBox.Y
		} else {
			if item.BBox.Y < minCross {
				minCross = item.BBox.Y
			}
			if item.BBox.Y > maxCross {
				maxCross = item.BBox.Y
			}
			gap := item.BBox.X - copied[i-1].BBox.Right()
			if gap > 0 {
				gaps = append(gaps, gap)
			}
		}
	}
	containerSize := box.Width
	if direction == "vertical" {
		containerSize = box.Height
	}
	out := validationMetrics{
		BBox:         box,
		RequiredSize: required,
		CrossSpread:  maxCross - minCross,
		MedianCross:  median(crossValues),
		MaxGap:       maxSlice(gaps),
		GapVariance:  variance(gaps),
	}
	if containerSize > 0 {
		out.FitRatio = float64(required) / float64(containerSize)
	}
	return out
}

func maxSlice(values []int) int {
	out := 0
	for _, value := range values {
		if value > out {
			out = value
		}
	}
	return out
}

func validateStyle(batchID string, evidenceByID map[string]EvidenceItem, id string, style ElementStyle) *RejectedStyle {
	item, ok := evidenceByID[id]
	if !ok {
		return &RejectedStyle{BatchID: batchID, EvidenceID: id, Reason: "unknown_evidence_id"}
	}
	if !textRole(item.RoleHint) {
		return &RejectedStyle{BatchID: batchID, EvidenceID: id, Reason: "style_allowed_only_for_text"}
	}
	if style.FontSize != 0 && (style.FontSize < 8 || style.FontSize > 72) {
		return &RejectedStyle{BatchID: batchID, EvidenceID: id, Reason: "font_size_out_of_range"}
	}
	if strings.TrimSpace(style.Color) != "" && !validHexColor(style.Color) {
		return &RejectedStyle{BatchID: batchID, EvidenceID: id, Reason: "invalid_color"}
	}
	return nil
}

func batchRejectSummary(rejected []RejectedGroup, batchID string) string {
	counts := map[string]int{}
	for _, item := range rejected {
		if item.BatchID != batchID {
			continue
		}
		counts[item.Reason]++
	}
	keys := make([]string, 0, len(counts))
	for key := range counts {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	parts := make([]string, 0, len(keys))
	for _, key := range keys {
		parts = append(parts, fmt.Sprintf("%s=%d", key, counts[key]))
	}
	return strings.Join(parts, ";")
}

func batchValidated(items []BatchValidation, batchID string) bool {
	for _, item := range items {
		if item.BatchID == batchID {
			return true
		}
	}
	return false
}

func summarizeValidation(validation Validation, totalEvidence map[string]bool) ValidationSummary {
	acceptedEvidence := map[string]bool{}
	for _, group := range validation.AcceptedGroups {
		for _, id := range group.EvidenceIDs {
			acceptedEvidence[id] = true
		}
	}
	summary := ValidationSummary{
		BatchCount:            len(validation.Batches),
		AcceptedGroupCount:    len(validation.AcceptedGroups),
		RejectedGroupCount:    len(validation.RejectedGroups),
		AcceptedStyleCount:    len(validation.AcceptedStyles),
		RejectedStyleCount:    len(validation.RejectedStyles),
		AcceptedEvidenceCount: len(acceptedEvidence),
		TotalEvidenceCount:    len(totalEvidence),
	}
	for _, batch := range validation.Batches {
		if batch.Fallback {
			summary.FallbackBatchCount++
		}
	}
	if summary.TotalEvidenceCount > 0 {
		summary.Coverage = float64(summary.AcceptedEvidenceCount) / float64(summary.TotalEvidenceCount)
	}
	return summary
}
