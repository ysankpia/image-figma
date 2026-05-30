package audit

import (
	"encoding/json"
	"fmt"
	"math"
	"os"
	"sort"
	"strings"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/diff"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/ir"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/contract"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/evidence"
)

func Compile(options Options) (Document, error) {
	if options.DiffPath == "" {
		return Document{}, fmt.Errorf("missing diff path")
	}
	doc, err := readDiff(options.DiffPath)
	if err != nil {
		return Document{}, err
	}
	var source sourceEvidence
	if options.TokenPath != "" {
		source.Tokens, err = readTokens(options.TokenPath)
		if err != nil {
			return Document{}, fmt.Errorf("read tokens: %w", err)
		}
		source.TokenPath = options.TokenPath
	}
	if options.PhysicalPath != "" {
		source.Physical, err = readPhysical(options.PhysicalPath)
		if err != nil {
			return Document{}, fmt.Errorf("read physical evidence: %w", err)
		}
		source.PhysicalPath = options.PhysicalPath
	}
	out := AnalyzeWithEvidence(doc, source)
	out.Source.DiffPath = options.DiffPath
	return out, nil
}

func Analyze(doc diff.Document) Document {
	return AnalyzeWithEvidence(doc, sourceEvidence{})
}

func AnalyzeWithEvidence(doc diff.Document, source sourceEvidence) Document {
	records := failureRecords(doc)
	groups := buildGroups(records)
	return Document{
		SchemaName: SchemaName,
		Version:    Version,
		Source: Source{
			GeneratedPath:        doc.Source.GeneratedPath,
			GoldenPath:           doc.Source.GoldenPath,
			EvidenceTokenPath:    source.TokenPath,
			PhysicalEvidencePath: source.PhysicalPath,
		},
		Summary: Summary{
			GeneratedNodeCount: doc.Summary.GeneratedNodeCount,
			GoldenNodeCount:    doc.Summary.GoldenNodeCount,
			MatchedNodeCount:   doc.Summary.MatchedNodeCount,
			ExtraNodeCount:     doc.Summary.ExtraNodeCount,
			MissedNodeCount:    doc.Summary.MissedNodeCount,
			ByStage:            countBy(records, func(r failureRecord) string { return nonEmpty(r.Stage, "unknown") }),
			ByDiagnosis:        countBy(records, func(r failureRecord) string { return nonEmpty(r.Diagnosis, "unknown") }),
			ByRole:             countBy(records, func(r failureRecord) string { return string(r.Role) }),
			ByEvidenceKind:     countBy(records, func(r failureRecord) string { return nonEmpty(r.EvidenceKind, "none") }),
			ByIoUBucket:        countBy(records, func(r failureRecord) string { return r.IoUBucket }),
		},
		Groups:    groups,
		Actions:   buildActions(groups),
		LeafDebug: buildLeafDebug(records, source),
	}
}

type sourceEvidence struct {
	TokenPath    string
	PhysicalPath string
	Tokens       []evidence.Token
	Physical     []contract.Primitive
}

func readDiff(path string) (diff.Document, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return diff.Document{}, err
	}
	var doc diff.Document
	if err := json.Unmarshal(data, &doc); err != nil {
		return diff.Document{}, err
	}
	if doc.SchemaName != diff.SchemaName {
		return diff.Document{}, fmt.Errorf("expected %s, got %q", diff.SchemaName, doc.SchemaName)
	}
	return doc, nil
}

func failureRecords(doc diff.Document) []failureRecord {
	var out []failureRecord
	for _, node := range doc.Generated {
		if node.Verdict != "extra" {
			continue
		}
		out = append(out, failureRecord{
			ID:                   node.ID,
			Role:                 node.Role,
			Stage:                nonEmpty(node.FailureStage, stageForRole(node.Role)),
			Diagnosis:            diagnoseGenerated(node),
			EvidenceKind:         node.EvidenceKind,
			EvidenceSourceID:     node.EvidenceSourceID,
			EvidenceNotes:        node.EvidenceNotes,
			SourcePath:           node.SourcePath,
			SourceGUID:           node.SourceGUID,
			IoUBucket:            iouBucket(node.BestIoU),
			Verdict:              node.Verdict,
			FailureReason:        node.FailureReason,
			ParentMatched:        node.ParentMatched,
			BestIoU:              node.BestIoU,
			ChildRoleCount:       node.ChildRoleCount,
			BestID:               node.BestID,
			BestEvidenceKind:     node.BestEvidenceKind,
			BestEvidenceSourceID: node.BestEvidenceSourceID,
			BestEvidenceNotes:    node.BestEvidenceNotes,
			BestSourcePath:       node.BestSourcePath,
			BestSourceGUID:       node.BestSourceGUID,
			BestBBox:             node.BestBBox,
			BestParentID:         node.BestParentID,
			ParentID:             node.ParentID,
			BBox:                 node.BBox,
		})
	}
	for _, node := range doc.Golden {
		if node.Verdict != "missed" {
			continue
		}
		out = append(out, failureRecord{
			ID:                   node.ID,
			Role:                 node.Role,
			Stage:                nonEmpty(node.FailureStage, stageForRole(node.Role)),
			Diagnosis:            diagnoseGolden(node),
			EvidenceKind:         "golden",
			EvidenceSourceID:     node.EvidenceSourceID,
			EvidenceNotes:        node.EvidenceNotes,
			SourcePath:           node.SourcePath,
			SourceGUID:           node.SourceGUID,
			IoUBucket:            iouBucket(node.BestIoU),
			Verdict:              node.Verdict,
			FailureReason:        node.FailureReason,
			ParentMatched:        node.ParentMatched,
			BestIoU:              node.BestIoU,
			ChildRoleCount:       node.ChildRoleCount,
			BestID:               node.BestID,
			BestEvidenceKind:     node.BestEvidenceKind,
			BestEvidenceSourceID: node.BestEvidenceSourceID,
			BestEvidenceNotes:    node.BestEvidenceNotes,
			BestSourcePath:       node.BestSourcePath,
			BestSourceGUID:       node.BestSourceGUID,
			BestBBox:             node.BestBBox,
			BestParentID:         node.BestParentID,
			ParentID:             node.ParentID,
			BBox:                 node.BBox,
		})
	}
	return out
}

func readTokens(path string) ([]evidence.Token, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var doc evidence.Document
	if err := json.Unmarshal(data, &doc); err != nil {
		return nil, err
	}
	if doc.SchemaName != "M29EvidenceTokens" {
		return nil, fmt.Errorf("expected M29EvidenceTokens, got %q", doc.SchemaName)
	}
	return doc.Tokens, nil
}

func readPhysical(path string) ([]contract.Primitive, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var doc contract.Document
	if err := json.Unmarshal(data, &doc); err != nil {
		return nil, err
	}
	if doc.SchemaName != "M29PhysicalEvidence" {
		return nil, fmt.Errorf("expected M29PhysicalEvidence, got %q", doc.SchemaName)
	}
	return doc.Primitives, nil
}

func buildLeafDebug(records []failureRecord, source sourceEvidence) []DebugSample {
	var samples []DebugSample
	for _, record := range records {
		if !leafDebugWorthy(record) {
			continue
		}
		sample := DebugSample{
			ID:                   record.ID,
			Verdict:              record.Verdict,
			Diagnosis:            record.Diagnosis,
			Role:                 string(record.Role),
			EvidenceKind:         record.EvidenceKind,
			EvidenceSourceID:     record.EvidenceSourceID,
			EvidenceNotes:        record.EvidenceNotes,
			SourcePath:           record.SourcePath,
			SourceGUID:           record.SourceGUID,
			ParentID:             record.ParentID,
			BBox:                 record.BBox,
			BestID:               record.BestID,
			BestEvidenceKind:     record.BestEvidenceKind,
			BestEvidenceSourceID: record.BestEvidenceSourceID,
			BestEvidenceNotes:    record.BestEvidenceNotes,
			BestSourcePath:       record.BestSourcePath,
			BestSourceGUID:       record.BestSourceGUID,
			BestParentID:         record.BestParentID,
			BestBBox:             record.BestBBox,
			BestIoU:              record.BestIoU,
			FailureReason:        record.FailureReason,
		}
		if record.Verdict == "missed" {
			sample.NearbyTokens = nearbyTokens(record.BBox, source.Tokens, 8)
			sample.NearbyPrimitives = nearbyPrimitives(record.BBox, source.Physical, 8)
		}
		samples = append(samples, sample)
	}
	sort.SliceStable(samples, func(i, j int) bool {
		wi, wj := debugSampleWeight(samples[i]), debugSampleWeight(samples[j])
		if wi != wj {
			return wi > wj
		}
		if samples[i].BestIoU != samples[j].BestIoU {
			return samples[i].BestIoU < samples[j].BestIoU
		}
		if samples[i].BBox.Y != samples[j].BBox.Y {
			return samples[i].BBox.Y < samples[j].BBox.Y
		}
		if samples[i].BBox.X != samples[j].BBox.X {
			return samples[i].BBox.X < samples[j].BBox.X
		}
		return samples[i].ID < samples[j].ID
	})
	if len(samples) > 24 {
		return samples[:24]
	}
	return samples
}

func nearbyTokens(target ir.BBox, tokens []evidence.Token, limit int) []NearbyEvidence {
	if len(tokens) == 0 || target.Width <= 0 || target.Height <= 0 || limit <= 0 {
		return nil
	}
	items := make([]NearbyEvidence, 0, len(tokens))
	for _, token := range tokens {
		box := irBBox(token.BBox)
		item := nearbyEvidence(target, box)
		if !nearbyEnough(item, target, box) {
			continue
		}
		item.ID = token.ID
		item.Kind = token.TokenType
		item.Disposition = token.Disposition
		item.Reasons = append([]string(nil), token.Reasons...)
		item.SourcePrimitiveIDs = append([]string(nil), token.SourcePrimitiveIDs...)
		item.MeanColor = token.Measurements.MeanColor
		item.TextureScore = token.Measurements.TextureScore
		items = append(items, item)
	}
	sortNearby(items)
	if len(items) > limit {
		return items[:limit]
	}
	return items
}

func nearbyPrimitives(target ir.BBox, primitives []contract.Primitive, limit int) []NearbyEvidence {
	if len(primitives) == 0 || target.Width <= 0 || target.Height <= 0 || limit <= 0 {
		return nil
	}
	items := make([]NearbyEvidence, 0, len(primitives))
	for _, primitive := range primitives {
		box := irBBox(primitive.BBox)
		item := nearbyEvidence(target, box)
		if !nearbyEnough(item, target, box) {
			continue
		}
		item.ID = primitive.ID
		item.Kind = primitive.PrimitiveType
		item.Reasons = append([]string(nil), primitive.CompileHints.Reasons...)
		item.MeanColor = primitive.Measurements.MeanColor
		item.TextureScore = primitive.Measurements.TextureScore
		item.EdgeDensity = primitive.Measurements.EdgeDensity
		item.ColorCount = primitive.Measurements.ColorCount
		items = append(items, item)
	}
	sortNearby(items)
	if len(items) > limit {
		return items[:limit]
	}
	return items
}

func nearbyEvidence(target ir.BBox, box ir.BBox) NearbyEvidence {
	return NearbyEvidence{
		BBox:           box,
		IoU:            round3(iou(target, box)),
		OverlapRatio:   round3(overlapRatio(target, box)),
		CenterDistance: round3(centerDistance(target, box)),
		Contained:      contains(box, target, 2),
		ContainsTarget: contains(target, box, 2),
	}
}

func nearbyEnough(item NearbyEvidence, target ir.BBox, box ir.BBox) bool {
	if item.IoU > 0 || item.OverlapRatio > 0 || item.Contained || item.ContainsTarget {
		return true
	}
	maxDistance := float64(maxInt(maxInt(target.Width, target.Height), 24) * 2)
	return item.CenterDistance <= maxDistance
}

func sortNearby(items []NearbyEvidence) {
	sort.SliceStable(items, func(i, j int) bool {
		if items[i].IoU != items[j].IoU {
			return items[i].IoU > items[j].IoU
		}
		if items[i].OverlapRatio != items[j].OverlapRatio {
			return items[i].OverlapRatio > items[j].OverlapRatio
		}
		if items[i].Contained != items[j].Contained {
			return items[i].Contained
		}
		if items[i].ContainsTarget != items[j].ContainsTarget {
			return items[i].ContainsTarget
		}
		if items[i].CenterDistance != items[j].CenterDistance {
			return items[i].CenterDistance < items[j].CenterDistance
		}
		return items[i].ID < items[j].ID
	})
}

func irBBox(box contract.BBox) ir.BBox {
	return ir.BBox{X: box.X, Y: box.Y, Width: box.Width, Height: box.Height}
}

func iou(a ir.BBox, b ir.BBox) float64 {
	intersection := intersectionArea(a, b)
	if intersection <= 0 {
		return 0
	}
	union := area(a) + area(b) - intersection
	if union <= 0 {
		return 0
	}
	return float64(intersection) / float64(union)
}

func overlapRatio(target ir.BBox, candidate ir.BBox) float64 {
	intersection := intersectionArea(target, candidate)
	if intersection <= 0 {
		return 0
	}
	return float64(intersection) / float64(maxInt(1, area(target)))
}

func intersectionArea(a ir.BBox, b ir.BBox) int {
	x1 := maxInt(a.X, b.X)
	y1 := maxInt(a.Y, b.Y)
	x2 := minInt(a.X+a.Width, b.X+b.Width)
	y2 := minInt(a.Y+a.Height, b.Y+b.Height)
	if x2 <= x1 || y2 <= y1 {
		return 0
	}
	return (x2 - x1) * (y2 - y1)
}

func centerDistance(a ir.BBox, b ir.BBox) float64 {
	ax := float64(a.X) + float64(a.Width)/2
	ay := float64(a.Y) + float64(a.Height)/2
	bx := float64(b.X) + float64(b.Width)/2
	by := float64(b.Y) + float64(b.Height)/2
	return math.Hypot(ax-bx, ay-by)
}

func contains(parent ir.BBox, child ir.BBox, tolerance int) bool {
	return parent.X-tolerance <= child.X &&
		parent.Y-tolerance <= child.Y &&
		parent.X+parent.Width+tolerance >= child.X+child.Width &&
		parent.Y+parent.Height+tolerance >= child.Y+child.Height
}

func area(box ir.BBox) int {
	return maxInt(0, box.Width) * maxInt(0, box.Height)
}

func minInt(a int, b int) int {
	if a < b {
		return a
	}
	return b
}

func maxInt(a int, b int) int {
	if a > b {
		return a
	}
	return b
}

func round3(value float64) float64 {
	return math.Round(value*1000) / 1000
}

func leafDebugWorthy(record failureRecord) bool {
	switch record.Role {
	case ir.RoleImageView, ir.RoleBackground, ir.RoleBgButton, ir.RoleBgEditText, ir.RoleTextView:
	default:
		return false
	}
	switch record.Diagnosis {
	case "upstream_leaf_missing",
		"leaf_bbox_too_large_or_shifted",
		"image_bbox_mismatch",
		"extra_image_leaf",
		"background_fragment_extra",
		"missing_background_surface",
		"background_bbox_mismatch",
		"text_bbox_mismatch",
		"extra_text_leaf",
		"missing_text_leaf":
		return true
	default:
		return false
	}
}

func debugSampleWeight(sample DebugSample) int {
	switch sample.Diagnosis {
	case "upstream_leaf_missing":
		return 100
	case "leaf_bbox_too_large_or_shifted", "image_bbox_mismatch":
		return 90
	case "missing_background_surface", "background_bbox_mismatch":
		return 80
	case "background_fragment_extra":
		return 70
	case "text_bbox_mismatch":
		return 60
	default:
		return 10
	}
}

func diagnoseGenerated(node diff.NodeMatch) string {
	if node.FailureReason == "parent_edge_mismatch" || (!node.ParentMatched && node.BestIoU >= 0.60) {
		return "tree_parent_mismatch"
	}
	switch node.Role {
	case ir.RoleTextView:
		if node.BestIoU > 0 && node.BestIoU < 0.60 {
			return "text_bbox_mismatch"
		}
		return "extra_text_leaf"
	case ir.RoleImageView:
		if node.BestIoU >= 0.30 && node.BestIoU < 0.60 {
			return "image_bbox_mismatch"
		}
		return "extra_image_leaf"
	case ir.RoleBackground, ir.RoleBgButton, ir.RoleBgEditText:
		if strings.Contains(node.EvidenceKind, "surface") || strings.Contains(node.EvidenceKind, "background") {
			return "background_fragment_extra"
		}
		return "extra_background_leaf"
	case ir.RoleButton, ir.RoleEditText:
		return "control_extra"
	case ir.RoleViewGroup, ir.RoleListView, ir.RoleActionBar, ir.RoleStatusBar, ir.RoleBottomNavigation:
		if node.BestIoU > 0 && node.BestIoU < 0.60 {
			return "tree_container_bbox_mismatch"
		}
		return "tree_container_extra"
	default:
		return "extra_node"
	}
}

func diagnoseGolden(node diff.NodeMatch) string {
	if node.FailureReason == "parent_edge_mismatch" || (!node.ParentMatched && node.BestIoU >= 0.60) {
		return "tree_parent_mismatch"
	}
	switch node.Role {
	case ir.RoleTextView:
		if node.BestIoU > 0 && node.BestIoU < 0.60 {
			return "text_bbox_mismatch"
		}
		return "missing_text_leaf"
	case ir.RoleImageView:
		if node.BestIoU >= 0.30 && node.BestIoU < 0.60 {
			return "leaf_bbox_too_large_or_shifted"
		}
		return "upstream_leaf_missing"
	case ir.RoleBackground, ir.RoleBgButton, ir.RoleBgEditText:
		if node.BestIoU > 0 && node.BestIoU < 0.60 {
			return "background_bbox_mismatch"
		}
		return "missing_background_surface"
	case ir.RoleButton, ir.RoleEditText:
		return "control_missing"
	case ir.RoleViewGroup, ir.RoleListView, ir.RoleActionBar, ir.RoleStatusBar, ir.RoleBottomNavigation:
		if node.BestIoU > 0 && node.BestIoU < 0.60 {
			return "tree_container_bbox_mismatch"
		}
		return "tree_container_missing"
	default:
		return "missing_node"
	}
}

func buildGroups(records []failureRecord) []Group {
	byKey := map[string]*Group{}
	for _, record := range records {
		role := string(record.Role)
		evidence := nonEmpty(record.EvidenceKind, "none")
		key := strings.Join([]string{record.Stage, record.Diagnosis, role, evidence}, "|")
		group := byKey[key]
		if group == nil {
			group = &Group{
				Key:          key,
				Stage:        record.Stage,
				Diagnosis:    record.Diagnosis,
				Role:         role,
				EvidenceKind: evidence,
			}
			byKey[key] = group
		}
		group.Count++
		if len(group.SampleIDs) < 8 {
			group.SampleIDs = append(group.SampleIDs, record.ID)
		}
	}
	out := make([]Group, 0, len(byKey))
	for _, group := range byKey {
		out = append(out, *group)
	}
	sort.SliceStable(out, func(i, j int) bool {
		if out[i].Count != out[j].Count {
			return out[i].Count > out[j].Count
		}
		return out[i].Key < out[j].Key
	})
	return out
}

func buildActions(groups []Group) []ActionItem {
	var out []ActionItem
	for _, group := range groups {
		item := ActionItem{
			OwnerLayer:   ownerLayer(group),
			Diagnosis:    group.Diagnosis,
			Role:         group.Role,
			EvidenceKind: group.EvidenceKind,
			Count:        group.Count,
			Rationale:    rationale(group),
			SampleIDs:    group.SampleIDs,
		}
		if item.OwnerLayer == "" {
			continue
		}
		out = append(out, item)
	}
	sort.SliceStable(out, func(i, j int) bool {
		wi, wj := actionWeight(out[i]), actionWeight(out[j])
		if wi != wj {
			return wi > wj
		}
		if out[i].Count != out[j].Count {
			return out[i].Count > out[j].Count
		}
		return out[i].Diagnosis < out[j].Diagnosis
	})
	if len(out) > 12 {
		out = out[:12]
	}
	for i := range out {
		out[i].Rank = i + 1
	}
	return out
}

func ownerLayer(group Group) string {
	switch group.Diagnosis {
	case "upstream_leaf_missing", "leaf_bbox_too_large_or_shifted", "image_bbox_mismatch", "extra_image_leaf", "missing_text_leaf", "text_bbox_mismatch", "extra_text_leaf":
		return "m29_physical_evidence_or_codia_leaf"
	case "background_fragment_extra", "missing_background_surface", "background_bbox_mismatch", "extra_background_leaf":
		return "background_detection_or_permission"
	case "control_missing", "control_extra":
		return "control_synthesis"
	case "tree_container_missing", "tree_container_extra", "tree_container_bbox_mismatch", "tree_parent_mismatch":
		return "codia_tree_builder"
	default:
		return group.Stage
	}
}

func rationale(group Group) string {
	switch group.Diagnosis {
	case "upstream_leaf_missing":
		return "golden leaf has no usable generated same-role crop; fix source primitive or leaf extraction before changing tree ownership"
	case "leaf_bbox_too_large_or_shifted", "image_bbox_mismatch":
		return "same-role image exists but IoU is below match threshold; crop granularity or bbox fitting is wrong"
	case "background_fragment_extra":
		return "generated background-like surface is not matched; decide whether to merge, consume, or suppress it before final tree emission"
	case "missing_background_surface", "background_bbox_mismatch":
		return "golden background surface is absent or poorly fit; fix background detection and permission separately from control synthesis"
	case "tree_parent_mismatch":
		return "node geometry can match but ownership differs; fix role-aware tree attachment"
	case "tree_container_bbox_mismatch", "tree_container_missing", "tree_container_extra":
		return "container evidence or bbox fitting is wrong; fix tree proposal logic without fabricating leaves"
	case "control_missing", "control_extra":
		return "control role synthesis disagrees with golden; inspect explicit background and foreground evidence gates"
	case "text_bbox_mismatch":
		return "OCR text exists but bbox does not match golden; fix text fitting rather than grouping"
	default:
		return "inspect this failure group before changing generation logic"
	}
}

func actionWeight(item ActionItem) int {
	weight := item.Count
	switch item.Diagnosis {
	case "upstream_leaf_missing":
		weight += 1000
	case "leaf_bbox_too_large_or_shifted", "image_bbox_mismatch":
		weight += 800
	case "missing_background_surface", "background_fragment_extra", "background_bbox_mismatch":
		weight += 650
	case "tree_parent_mismatch":
		weight += 500
	case "tree_container_missing", "tree_container_bbox_mismatch":
		weight += 420
	case "control_missing", "control_extra":
		weight += 350
	}
	return weight
}

func countBy(records []failureRecord, key func(failureRecord) string) map[string]int {
	out := map[string]int{}
	for _, record := range records {
		out[nonEmpty(key(record), "unknown")]++
	}
	return out
}

func iouBucket(value float64) string {
	switch {
	case value <= 0:
		return "0"
	case value < 0.30:
		return "0-0.30"
	case value < 0.60:
		return "0.30-0.60"
	default:
		return "0.60+"
	}
}

func stageForRole(role ir.Role) string {
	switch role {
	case ir.RoleTextView, ir.RoleImageView, ir.RoleBackground, ir.RoleBgButton, ir.RoleBgEditText:
		return "leaf_or_background"
	case ir.RoleButton, ir.RoleEditText:
		return "control_synthesis"
	case ir.RoleActionBar, ir.RoleStatusBar, ir.RoleBottomNavigation, ir.RoleListView, ir.RoleViewGroup:
		return "tree_builder"
	default:
		return "unknown"
	}
}

func nonEmpty(value string, fallback string) string {
	if value == "" {
		return fallback
	}
	return value
}
