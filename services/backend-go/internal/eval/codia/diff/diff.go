package diff

import (
	"encoding/json"
	"fmt"
	"os"
	"sort"
	"strconv"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/eval/codia/ir"
)

const matchIoUThreshold = 0.60

func Compile(options Options) (Document, error) {
	if options.GeneratedPath == "" {
		return Document{}, fmt.Errorf("missing generated path")
	}
	if options.GoldenPath == "" {
		return Document{}, fmt.Errorf("missing golden path")
	}
	generated, err := readIR(options.GeneratedPath)
	if err != nil {
		return Document{}, fmt.Errorf("read generated: %w", err)
	}
	golden, err := readIR(options.GoldenPath)
	if err != nil {
		return Document{}, fmt.Errorf("read golden: %w", err)
	}
	out, err := Compare(generated, golden)
	if err != nil {
		return Document{}, err
	}
	out.Source.GeneratedPath = options.GeneratedPath
	out.Source.GoldenPath = options.GoldenPath
	return out, nil
}

func Compare(generated ir.Document, golden ir.Document) (Document, error) {
	if generated.SchemaName != ir.SchemaName {
		return Document{}, fmt.Errorf("generated expected %s, got %q", ir.SchemaName, generated.SchemaName)
	}
	if golden.SchemaName != ir.SchemaName {
		return Document{}, fmt.Errorf("golden expected %s, got %q", ir.SchemaName, golden.SchemaName)
	}
	genRecords := flatten(generated.Root)
	goldRecords := flatten(golden.Root)
	genMatches := bestMatches(genRecords, goldRecords)
	goldMatches := bestMatches(goldRecords, genRecords)
	genNodeMatches := buildGeneratedMatches(genRecords, genMatches, goldMatches)
	goldNodeMatches := buildGoldenMatches(goldRecords, goldMatches, genMatches)
	checks := buildChecks(genRecords)
	edges := buildEdgeSummary(genRecords, goldRecords, genMatches, goldMatches)
	doc := Document{
		SchemaName: SchemaName,
		Version:    Version,
		Summary:    buildSummary(genNodeMatches, goldNodeMatches),
		Checks:     checks,
		Generated:  genNodeMatches,
		Golden:     goldNodeMatches,
		Edges:      edges,
	}
	return doc, nil
}

func readIR(path string) (ir.Document, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return ir.Document{}, err
	}
	var doc ir.Document
	if err := json.Unmarshal(data, &doc); err != nil {
		return ir.Document{}, err
	}
	if doc.SchemaName != ir.SchemaName {
		return ir.Document{}, fmt.Errorf("expected %s, got %q", ir.SchemaName, doc.SchemaName)
	}
	return doc, nil
}

func flatten(root ir.Node) []*nodeRecord {
	out := []*nodeRecord{}
	var walk func(ir.Node, *nodeRecord, string) *nodeRecord
	walk = func(node ir.Node, parent *nodeRecord, path string) *nodeRecord {
		record := &nodeRecord{Node: node, Parent: parent, Path: path}
		out = append(out, record)
		for i, child := range node.Children {
			childRecord := walk(child, record, childPath(path, i))
			record.Children = append(record.Children, childRecord)
		}
		return record
	}
	walk(root, nil, "/")
	return out
}

func childPath(path string, index int) string {
	if path == "/" {
		return "/" + strconv.Itoa(index)
	}
	return path + "/" + strconv.Itoa(index)
}

func bestMatches(from []*nodeRecord, to []*nodeRecord) map[*nodeRecord]*nodeRecord {
	out := map[*nodeRecord]*nodeRecord{}
	for _, source := range from {
		var best *nodeRecord
		bestScore := -1.0
		for _, candidate := range to {
			if candidate.Node.Role != source.Node.Role {
				continue
			}
			score := iou(source.Node.FigmaBBox, candidate.Node.FigmaBBox)
			if score > bestScore || (score == bestScore && candidate.Node.ID < best.Node.ID) {
				bestScore = score
				best = candidate
			}
		}
		if best != nil {
			out[source] = best
		}
	}
	return out
}

func buildGeneratedMatches(records []*nodeRecord, matches map[*nodeRecord]*nodeRecord, reverse map[*nodeRecord]*nodeRecord) []NodeMatch {
	out := make([]NodeMatch, 0, len(records))
	for _, record := range records {
		best := matches[record]
		match := nodeMatch(record, best)
		if best != nil && reverse[best] == record && match.BestIoU >= matchIoUThreshold {
			match.Verdict = "matched"
		} else {
			match.Verdict = "extra"
			match.FailureStage = failureStage(record)
			match.FailureReason = failureReason(record, best, reverse)
		}
		match.ParentMatched = parentMatched(record, best)
		out = append(out, match)
	}
	sortNodeMatches(out)
	return out
}

func buildGoldenMatches(records []*nodeRecord, matches map[*nodeRecord]*nodeRecord, reverse map[*nodeRecord]*nodeRecord) []NodeMatch {
	out := make([]NodeMatch, 0, len(records))
	for _, record := range records {
		best := matches[record]
		match := nodeMatch(record, best)
		if best != nil && reverse[best] == record && match.BestIoU >= matchIoUThreshold {
			match.Verdict = "matched"
		} else {
			match.Verdict = "missed"
			match.FailureStage = failureStage(record)
			match.FailureReason = failureReason(record, best, nil)
		}
		match.ParentMatched = parentMatched(record, best)
		out = append(out, match)
	}
	sortNodeMatches(out)
	return out
}

func nodeMatch(record *nodeRecord, best *nodeRecord) NodeMatch {
	match := NodeMatch{
		ID:               record.Node.ID,
		Role:             record.Node.Role,
		ParentID:         parentID(record),
		Path:             record.Path,
		SchemaID:         record.Node.SchemaID,
		EvidenceKind:     firstEvidenceKind(record.Node),
		EvidenceSourceID: firstEvidenceSourceID(record.Node),
		EvidenceNotes:    firstEvidenceNotes(record.Node),
		SourcePath:       record.Node.SourcePath,
		SourceGUID:       record.Node.SourceGUID,
		VisibleName:      record.Node.VisibleName,
		FigmaType:        string(record.Node.FigmaType),
		BBox:             record.Node.FigmaBBox,
		Verdict:          "unmatched",
		ChildRoleCount:   len(record.Node.Children),
	}
	if best != nil {
		match.BestID = best.Node.ID
		match.BestRole = best.Node.Role
		match.BestParentID = parentID(best)
		match.BestPath = best.Path
		match.BestSchemaID = best.Node.SchemaID
		match.BestEvidenceKind = firstEvidenceKind(best.Node)
		match.BestEvidenceSourceID = firstEvidenceSourceID(best.Node)
		match.BestEvidenceNotes = firstEvidenceNotes(best.Node)
		match.BestSourcePath = best.Node.SourcePath
		match.BestSourceGUID = best.Node.SourceGUID
		match.BestBBox = best.Node.FigmaBBox
		match.BestIoU = iou(record.Node.FigmaBBox, best.Node.FigmaBBox)
	}
	return match
}

func firstEvidenceKind(node ir.Node) string {
	if len(node.Evidence) == 0 {
		return ""
	}
	return node.Evidence[0].Kind
}

func firstEvidenceSourceID(node ir.Node) string {
	if len(node.Evidence) == 0 {
		return ""
	}
	return node.Evidence[0].SourceID
}

func firstEvidenceNotes(node ir.Node) string {
	if len(node.Evidence) == 0 {
		return ""
	}
	return node.Evidence[0].Notes
}

func sortNodeMatches(items []NodeMatch) {
	sort.SliceStable(items, func(i, j int) bool {
		if items[i].BBox.Y != items[j].BBox.Y {
			return items[i].BBox.Y < items[j].BBox.Y
		}
		if items[i].BBox.X != items[j].BBox.X {
			return items[i].BBox.X < items[j].BBox.X
		}
		if items[i].Role != items[j].Role {
			return items[i].Role < items[j].Role
		}
		return items[i].ID < items[j].ID
	})
}

func buildSummary(generated []NodeMatch, golden []NodeMatch) Summary {
	roles := map[string]Role{}
	extraByEvidence := map[string]int{}
	missedByEvidence := map[string]int{}
	totalBest := 0.0
	for _, item := range generated {
		role := roles[string(item.Role)]
		role.Generated++
		if item.Verdict == "matched" {
			role.Matched++
		} else {
			role.Extra++
			extraByEvidence[evidenceBucket(item.EvidenceKind)]++
		}
		roles[string(item.Role)] = role
		totalBest += item.BestIoU
	}
	for _, item := range golden {
		role := roles[string(item.Role)]
		role.Golden++
		if item.Verdict == "missed" {
			role.Missed++
			missedByEvidence[evidenceBucket(item.EvidenceKind)]++
		}
		roles[string(item.Role)] = role
	}
	matched, extra, missed := 0, 0, 0
	for key, role := range roles {
		role.Precision = ratio(role.Matched, role.Generated)
		role.Recall = ratio(role.Matched, role.Golden)
		roles[key] = role
		matched += role.Matched
		extra += role.Extra
		missed += role.Missed
	}
	return Summary{
		GeneratedNodeCount: len(generated),
		GoldenNodeCount:    len(golden),
		MatchedNodeCount:   matched,
		ExtraNodeCount:     extra,
		MissedNodeCount:    missed,
		RoleMetrics:        roles,
		ExtraByEvidence:    extraByEvidence,
		MissedByEvidence:   missedByEvidence,
		AverageBestIoU:     ratioFloat(totalBest, len(generated)),
	}
}

func evidenceBucket(kind string) string {
	if kind == "" {
		return "none"
	}
	return kind
}

func buildChecks(records []*nodeRecord) Checks {
	violations := visibleVocabularyViolations(records)
	return Checks{
		VisibleVocabularyPass:       len(violations) == 0,
		VisibleVocabularyViolations: violations,
		ButtonBackgroundLast:        controlBackgroundLast(records, ir.RoleButton, ir.RoleBgButton),
		EditTextBackgroundLast:      controlBackgroundLast(records, ir.RoleEditText, ir.RoleBgEditText),
		BackgroundLate:              backgroundLate(records),
	}
}

func visibleVocabularyViolations(records []*nodeRecord) []string {
	var out []string
	for _, record := range records {
		if visibleNameAllowed(record.Node) {
			continue
		}
		out = append(out, record.Node.ID)
	}
	return out
}

func visibleNameAllowed(node ir.Node) bool {
	switch node.Role {
	case ir.RoleRoot:
		return node.FigmaType == ir.FigmaFrame && node.VisibleName == "Root"
	case ir.RoleViewGroup, ir.RoleListView, ir.RoleActionBar, ir.RoleStatusBar, ir.RoleBottomNavigation:
		return node.FigmaType == ir.FigmaFrame && node.VisibleName == "Groups"
	case ir.RoleButton:
		return node.FigmaType == ir.FigmaFrame && node.VisibleName == "Button"
	case ir.RoleEditText:
		return node.FigmaType == ir.FigmaFrame && node.VisibleName == "Text"
	case ir.RoleTextView:
		return node.FigmaType == ir.FigmaText && node.Text != nil && node.VisibleName == node.Text.Characters
	case ir.RoleImageView:
		return node.FigmaType == ir.FigmaRoundedRectangle && node.VisibleName == "Image"
	case ir.RoleBackground, ir.RoleBgButton, ir.RoleBgEditText:
		return node.FigmaType == ir.FigmaRoundedRectangle && node.VisibleName == "Background"
	default:
		return false
	}
}

func controlBackgroundLast(records []*nodeRecord, controlRole ir.Role, backgroundRole ir.Role) LastRole {
	out := LastRole{Pass: true}
	for _, record := range records {
		if record.Node.Role != controlRole {
			continue
		}
		out.Total++
		if len(record.Children) > 0 && record.Children[len(record.Children)-1].Node.Role == backgroundRole {
			out.Passed++
			continue
		}
		out.Pass = false
		out.Violations = append(out.Violations, record.Node.ID)
	}
	return out
}

func backgroundLate(records []*nodeRecord) LastRole {
	out := LastRole{Pass: true}
	for _, record := range records {
		if len(record.Children) <= 1 {
			continue
		}
		lastBackgroundIndex := -1
		firstNonBackgroundAfter := -1
		for i, child := range record.Children {
			if isBackgroundRole(child.Node.Role) {
				lastBackgroundIndex = i
				continue
			}
			if lastBackgroundIndex != -1 {
				firstNonBackgroundAfter = i
				break
			}
		}
		if lastBackgroundIndex == -1 {
			continue
		}
		out.Total++
		if firstNonBackgroundAfter == -1 {
			out.Passed++
			continue
		}
		out.Pass = false
		out.Violations = append(out.Violations, record.Node.ID)
	}
	return out
}

func isBackgroundRole(role ir.Role) bool {
	return role == ir.RoleBackground || role == ir.RoleBgButton || role == ir.RoleBgEditText
}

func buildEdgeSummary(generated []*nodeRecord, golden []*nodeRecord, genMatches map[*nodeRecord]*nodeRecord, goldMatches map[*nodeRecord]*nodeRecord) EdgeSummary {
	out := EdgeSummary{}
	generatedMatched := 0
	goldenMatched := 0
	for _, record := range generated {
		if record.Parent == nil {
			continue
		}
		best := genMatches[record]
		verdict := edgeVerdict(record, best)
		if verdict.Verdict == "matched" {
			generatedMatched++
		} else if len(out.GeneratedSamples) < 25 {
			out.GeneratedSamples = append(out.GeneratedSamples, verdict)
		}
	}
	for _, record := range golden {
		if record.Parent == nil {
			continue
		}
		best := goldMatches[record]
		verdict := edgeVerdict(record, best)
		if verdict.Verdict == "matched" {
			goldenMatched++
		} else if len(out.GoldenSamples) < 25 {
			out.GoldenSamples = append(out.GoldenSamples, verdict)
		}
	}
	out.Compared = max(0, len(generated)-1)
	out.Matched = generatedMatched
	out.Precision = ratio(generatedMatched, max(0, len(generated)-1))
	out.Recall = ratio(goldenMatched, max(0, len(golden)-1))
	return out
}

func edgeVerdict(record *nodeRecord, best *nodeRecord) EdgeVerdict {
	out := EdgeVerdict{
		ChildID:    record.Node.ID,
		ChildRole:  record.Node.Role,
		ParentID:   parentID(record),
		ParentRole: parentRole(record),
		Verdict:    "extra",
	}
	if best == nil {
		return out
	}
	out.BestID = best.Node.ID
	out.BestParentID = parentID(best)
	out.BestParentRole = parentRole(best)
	if iou(record.Node.FigmaBBox, best.Node.FigmaBBox) < matchIoUThreshold {
		return out
	}
	if parentID(record) == parentID(best) || (record.Parent != nil && best.Parent != nil && record.Parent.Node.Role == best.Parent.Node.Role && iou(record.Parent.Node.FigmaBBox, best.Parent.Node.FigmaBBox) >= matchIoUThreshold) {
		out.Verdict = "matched"
	}
	return out
}

func parentMatched(record *nodeRecord, best *nodeRecord) bool {
	if record == nil || best == nil {
		return false
	}
	if record.Parent == nil && best.Parent == nil {
		return true
	}
	if record.Parent == nil || best.Parent == nil {
		return false
	}
	return record.Parent.Node.Role == best.Parent.Node.Role && iou(record.Parent.Node.FigmaBBox, best.Parent.Node.FigmaBBox) >= matchIoUThreshold
}

func failureStage(record *nodeRecord) string {
	switch record.Node.Role {
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

func failureReason(record *nodeRecord, best *nodeRecord, reverse map[*nodeRecord]*nodeRecord) string {
	if best == nil {
		return "no_same_role_candidate"
	}
	score := iou(record.Node.FigmaBBox, best.Node.FigmaBBox)
	if score < matchIoUThreshold {
		return "below_iou_threshold"
	}
	if reverse != nil && reverse[best] != record {
		return "not_reciprocal_best_match"
	}
	if !parentMatched(record, best) {
		return "parent_edge_mismatch"
	}
	return "unclassified_mismatch"
}

func parentID(record *nodeRecord) string {
	if record == nil || record.Parent == nil {
		return ""
	}
	return record.Parent.Node.ID
}

func parentRole(record *nodeRecord) ir.Role {
	if record == nil || record.Parent == nil {
		return ""
	}
	return record.Parent.Node.Role
}

func iou(a ir.BBox, b ir.BBox) float64 {
	intersection := intersectionArea(a, b)
	if intersection <= 0 {
		return 0
	}
	return float64(intersection) / float64(max(1, area(a)+area(b)-intersection))
}

func intersectionArea(a ir.BBox, b ir.BBox) int {
	x1 := max(a.X, b.X)
	y1 := max(a.Y, b.Y)
	x2 := min(a.X+a.Width, b.X+b.Width)
	y2 := min(a.Y+a.Height, b.Y+b.Height)
	if x2 <= x1 || y2 <= y1 {
		return 0
	}
	return (x2 - x1) * (y2 - y1)
}

func area(box ir.BBox) int {
	return max(0, box.Width) * max(0, box.Height)
}

func ratio(numerator int, denominator int) float64 {
	if denominator <= 0 {
		return 0
	}
	return float64(numerator) / float64(denominator)
}

func ratioFloat(numerator float64, denominator int) float64 {
	if denominator <= 0 {
		return 0
	}
	return numerator / float64(denominator)
}

func min(a int, b int) int {
	if a < b {
		return a
	}
	return b
}

func max(a int, b int) int {
	if a > b {
		return a
	}
	return b
}
