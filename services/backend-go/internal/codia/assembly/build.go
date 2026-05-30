package assembly

import (
	"fmt"
	"math"
	"sort"
	"strings"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/detector"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/ir"
)

const (
	decisionEmit     = "emit"
	decisionConsume  = "consume"
	decisionSuppress = "suppress"
	decisionRefine   = "refine"
	decisionHint     = "hint"
)

func Build(options Options) (Result, error) {
	if options.Leaf.SchemaName != ir.SchemaName {
		return Result{}, fmt.Errorf("expected %s leaf document, got %q", ir.SchemaName, options.Leaf.SchemaName)
	}
	b := builder{
		leaf:       options.Leaf,
		detector:   options.Detector,
		source:     Source{PhysicalPath: options.PhysicalPath, TokenPath: options.TokenPath, DetectorPath: options.DetectorPath, SourceOutputPath: options.SourceOutputPath},
		consumed:   map[string]bool{},
		suppressed: map[string]bool{},
	}
	doc := b.build()
	result := Result{
		SchemaName:       SchemaName,
		Version:          Version,
		Source:           b.source,
		Document:         doc,
		SourceCandidates: b.sourceCandidates(),
		OwnershipGraph:   b.ownershipGraph(),
		Diagnostics:      b.diagnostics(doc),
	}
	result.SourceCandidates.Source = result.Source
	result.OwnershipGraph.Source = result.Source
	return result, nil
}

type builder struct {
	leaf       ir.Document
	detector   *detector.Document
	source     Source
	consumed   map[string]bool
	suppressed map[string]bool
	emitted    []ir.Node
	records    []CandidateRecord
	graphNodes []OwnershipNode
	graphEdges []OwnershipEdge
	hints      []ir.Evidence
}

func (b *builder) build() ir.Document {
	for _, item := range b.detectorCandidates() {
		if isRegionHint(item.Role) {
			b.addDetectorHint(item)
			continue
		}
		if item.Role == detector.RoleButton {
			b.addDetectorOnlyRecord(item, decisionHint, 0.3, "detector_button_is_evidence_only", "none")
			continue
		}
		if item.Role == detector.RoleEditText {
			b.addDetectorOnlyRecord(item, decisionHint, 0.42, "detector_edittext_region_hint_only", "detector")
			continue
		}
		if item.Role == detector.RoleBackground {
			b.addDetectorOnlyRecord(item, decisionHint, 0.35, "detector_background_requires_permission_gate", "detector")
			continue
		}
		if item.Role != detector.RoleImageView || !detectorImageCandidateAccepted(item) {
			continue
		}
		b.mergeDetectorImage(item)
	}

	imageOwners := b.currentImageOwners()
	for _, node := range b.leaf.Root.Children {
		if b.consumed[node.ID] || b.suppressed[node.ID] {
			continue
		}
		switch node.Role {
		case ir.RoleImageView:
			if owner, ok := containedByLargeImageOwner(node, imageOwners); ok {
				b.consumeNode(node, owner.ID, 0.72, "m29_image_fragment_owned_by_larger_image", "m29")
				continue
			}
			b.emitLeaf(node, 0.66, "m29_independent_image_candidate", "m29")
			imageOwners = append(imageOwners, node)
		case ir.RoleTextView:
			if owner, ok := textOwnedByImage(node, imageOwners); ok {
				b.consumeNode(node, owner.ID, 0.68, "ocr_text_inside_image_owner", "image_owner")
				continue
			}
			b.emitLeaf(node, 0.82, "ocr_text_default_emit", "ocr")
		case ir.RoleBackground:
			if b.keepBackground(node) {
				b.emitLeaf(node, 0.61, "background_allowed_for_region_or_control", "m29")
				continue
			}
			b.suppressNode(node, 0.58, "background_fragment_without_owner", "m29")
		default:
			b.emitLeaf(node, 0.5, "unhandled_leaf_role_preserved", "m29")
		}
	}

	outRoot := b.leaf.Root
	outRoot.Children = append([]ir.Node{}, b.emitted...)
	outRoot.Evidence = append(outRoot.Evidence, b.hints...)
	sortNodes(outRoot.Children)
	assignSequences(&outRoot)

	out := b.leaf
	out.Source = b.leaf.Source
	if b.source.SourceOutputPath != "" {
		out.Source.InputPath = b.source.SourceOutputPath
	}
	out.Source.DesignFrameName = "Codia assembly source candidates"
	out.Root = outRoot
	out.Summary = summarize(outRoot)
	return out
}

func (b *builder) detectorCandidates() []detector.Candidate {
	if b.detector == nil {
		return nil
	}
	out := append([]detector.Candidate{}, b.detector.Candidates...)
	sort.SliceStable(out, func(i, j int) bool {
		if out[i].Confidence != out[j].Confidence {
			return out[i].Confidence > out[j].Confidence
		}
		if out[i].BBox.Y != out[j].BBox.Y {
			return out[i].BBox.Y < out[j].BBox.Y
		}
		if out[i].BBox.X != out[j].BBox.X {
			return out[i].BBox.X < out[j].BBox.X
		}
		return out[i].ID < out[j].ID
	})
	return out
}

func (b *builder) mergeDetectorImage(item detector.Candidate) {
	box := bboxFromDetector(item.BBox)
	if box.Width <= 0 || box.Height <= 0 {
		return
	}
	if owner, ok := b.findExistingImageOwner(box); ok {
		b.addDetectorOnlyRecord(item, decisionRefine, item.Confidence, "detector_refines_existing_image_owner", "detector")
		b.graphEdges = append(b.graphEdges, OwnershipEdge{
			FromID: item.ID,
			ToID:   owner.ID,
			Kind:   "refines_bbox",
			Score:  round3(item.Confidence),
			Reason: "detector_box_matches_existing_image",
		})
		return
	}
	matches := b.matchImageFragments(box)
	node := ir.Node{
		ID:          fmt.Sprintf("assembly_image_%04d", len(b.emitted)+1),
		Role:        ir.RoleImageView,
		SourceBBox:  box,
		FigmaBBox:   box,
		FigmaType:   ir.FigmaRoundedRectangle,
		VisibleName: "Image",
		SourcePath:  item.ID,
		Evidence: []ir.Evidence{{
			Kind:       "vision_detector_image_candidate",
			BBox:       box,
			Confidence: item.Confidence,
			SourceID:   item.ID,
			Notes:      detectorNotes(item),
		}},
		Asset: &ir.Asset{Kind: "crop", Hash: item.ID},
		Style: ir.Style{Visible: true, Opacity: 1},
	}
	for _, match := range matches {
		b.consumed[match.ID] = true
		node.Evidence = append(node.Evidence, match.Evidence...)
		b.recordLeaf(match, decisionConsume, item.Confidence, "m29_image_fragment_merged_into_detector_image", "detector", node.ID)
		b.graphEdges = append(b.graphEdges, OwnershipEdge{
			FromID: match.ID,
			ToID:   node.ID,
			Kind:   "merged_into",
			Score:  round3(overlapRatio(match.SourceBBox, box)),
			Reason: "detector_image_owns_m29_fragment",
		})
	}
	b.emitted = append(b.emitted, node)
	b.recordDetector(item, decisionEmit, item.Confidence, "detector_image_emitted_as_bbox_authority", "detector", node.ID)
	b.graphNodes = append(b.graphNodes, graphNode(node, decisionEmit, item.Confidence, "detector_image_emitted_as_bbox_authority", "detector", []string{item.ID}))
}

func (b *builder) findExistingImageOwner(box ir.BBox) (ir.Node, bool) {
	for _, node := range b.emitted {
		if node.Role != ir.RoleImageView {
			continue
		}
		if iou(node.SourceBBox, box) >= 0.72 {
			return node, true
		}
	}
	for _, node := range b.leaf.Root.Children {
		if b.consumed[node.ID] || b.suppressed[node.ID] || node.Role != ir.RoleImageView {
			continue
		}
		if iou(node.SourceBBox, box) >= 0.78 {
			b.consumed[node.ID] = true
			refined := node
			refined.SourceBBox = box
			refined.FigmaBBox = box
			refined.Evidence = append([]ir.Evidence{{
				Kind:       "vision_detector_image_bbox_refine",
				BBox:       box,
				Confidence: 0.8,
				SourceID:   node.ID,
				Notes:      "detector_bbox_authority",
			}}, node.Evidence...)
			b.emitted = append(b.emitted, refined)
			b.recordLeaf(node, decisionRefine, 0.8, "m29_image_bbox_refined_by_detector", "detector", refined.ID)
			b.graphNodes = append(b.graphNodes, graphNode(refined, decisionRefine, 0.8, "m29_image_bbox_refined_by_detector", "detector", []string{node.ID}))
			return refined, true
		}
	}
	return ir.Node{}, false
}

func (b *builder) matchImageFragments(box ir.BBox) []ir.Node {
	var out []ir.Node
	for _, node := range b.leaf.Root.Children {
		if b.consumed[node.ID] || b.suppressed[node.ID] || node.Role != ir.RoleImageView {
			continue
		}
		if overlapRatio(node.SourceBBox, box) >= 0.45 || centerInside(box, node.SourceBBox, 4) {
			out = append(out, node)
		}
	}
	sortNodes(out)
	return out
}

func (b *builder) currentImageOwners() []ir.Node {
	out := []ir.Node{}
	for _, node := range b.emitted {
		if node.Role == ir.RoleImageView {
			out = append(out, node)
		}
	}
	return out
}

func (b *builder) emitLeaf(node ir.Node, score float64, reason string, authority string) {
	if node.Style.Opacity == 0 && !node.Style.Visible {
		node.Style.Visible = true
		node.Style.Opacity = 1
	}
	b.emitted = append(b.emitted, node)
	b.recordLeaf(node, decisionEmit, score, reason, authority, node.ID)
	b.graphNodes = append(b.graphNodes, graphNode(node, decisionEmit, score, reason, authority, []string{node.ID}))
}

func (b *builder) consumeNode(node ir.Node, ownerID string, score float64, reason string, authority string) {
	b.consumed[node.ID] = true
	b.recordLeaf(node, decisionConsume, score, reason, authority, ownerID)
	b.graphNodes = append(b.graphNodes, graphNode(node, decisionConsume, score, reason, authority, []string{node.ID}))
	b.graphEdges = append(b.graphEdges, OwnershipEdge{FromID: node.ID, ToID: ownerID, Kind: "consumed_by", Score: round3(score), Reason: reason})
}

func (b *builder) suppressNode(node ir.Node, score float64, reason string, authority string) {
	b.suppressed[node.ID] = true
	b.recordLeaf(node, decisionSuppress, score, reason, authority, "")
	b.graphNodes = append(b.graphNodes, graphNode(node, decisionSuppress, score, reason, authority, []string{node.ID}))
}

func (b *builder) addDetectorHint(item detector.Candidate) {
	box := bboxFromDetector(item.BBox)
	evidence := ir.Evidence{
		Kind:       "assembly_region_hint",
		BBox:       box,
		Confidence: item.Confidence,
		SourceID:   item.ID,
		Notes:      fmt.Sprintf("%s/pass=%s/label=%s", item.Role, item.Source.PassID, item.RawLabel),
	}
	b.hints = append(b.hints, evidence)
	b.addDetectorOnlyRecord(item, decisionHint, item.Confidence, "detector_region_hint_only", "detector")
}

func (b *builder) addDetectorOnlyRecord(item detector.Candidate, decision string, score float64, reason string, authority string) {
	b.recordDetector(item, decision, score, reason, authority, "")
	b.graphNodes = append(b.graphNodes, OwnershipNode{
		ID:            item.ID,
		Role:          ir.Role(item.Role),
		BBox:          bboxFromDetector(item.BBox),
		Decision:      decision,
		Reason:        reason,
		Score:         round3(score),
		BBoxAuthority: authority,
		SourceIDs:     []string{item.ID},
	})
}

func (b *builder) keepBackground(node ir.Node) bool {
	box := node.SourceBBox
	root := b.leaf.Root.SourceBBox
	if area(box) <= 0 {
		return false
	}
	if bottomRegionBackground(box, root) || topRegionBackground(box, root) {
		return true
	}
	if !controlEligibleBackground(node, root) {
		return false
	}
	for _, candidate := range b.leaf.Root.Children {
		if candidate.ID == node.ID {
			continue
		}
		if candidate.Role != ir.RoleTextView && candidate.Role != ir.RoleImageView {
			continue
		}
		if centerInside(box, candidate.SourceBBox, 4) || overlapRatio(candidate.SourceBBox, box) >= 0.45 {
			return true
		}
	}
	return false
}

func (b *builder) sourceCandidates() SourceCandidatesDocument {
	summary := CandidateSummary{
		Total:      len(b.records),
		ByDecision: map[string]int{},
		ByRole:     map[string]int{},
	}
	for _, item := range b.records {
		summary.ByDecision[item.Decision]++
		summary.ByRole[string(item.Role)]++
		if item.Decision == decisionEmit || item.Decision == decisionRefine {
			summary.EmittedCount++
		}
		if item.Decision == decisionHint {
			summary.HintCount++
		}
	}
	return SourceCandidatesDocument{
		SchemaName: "CodiaSourceCandidates",
		Version:    "1.0",
		Candidates: append([]CandidateRecord{}, b.records...),
		Summary:    summary,
	}
}

func (b *builder) ownershipGraph() OwnershipGraphDocument {
	decisions := map[string]int{}
	for _, node := range b.graphNodes {
		decisions[node.Decision]++
	}
	return OwnershipGraphDocument{
		SchemaName: "CodiaOwnershipGraph",
		Version:    "1.0",
		Nodes:      append([]OwnershipNode{}, b.graphNodes...),
		Edges:      append([]OwnershipEdge{}, b.graphEdges...),
		Summary: GraphSummary{
			NodeCount: len(b.graphNodes),
			EdgeCount: len(b.graphEdges),
			Decisions: decisions,
		},
	}
}

func (b *builder) diagnostics(doc ir.Document) Diagnostics {
	roleCounts := map[string]int{}
	for role, count := range doc.Summary.RoleCounts {
		roleCounts[role] = count
	}
	d := Diagnostics{
		InputLeafCount:         len(b.leaf.Root.Children),
		OutputNodeCount:        len(doc.Root.Children),
		ConsumedCount:          len(b.consumed),
		SuppressedCount:        len(b.suppressed),
		HintCount:              len(b.hints),
		RoleCounts:             roleCounts,
		DetectorCandidateCount: 0,
	}
	if b.detector != nil {
		d.DetectorCandidateCount = len(b.detector.Candidates)
	}
	for _, item := range b.records {
		if item.Decision == decisionRefine {
			d.RefinedCount++
		}
	}
	return d
}

func (b *builder) recordLeaf(node ir.Node, decision string, score float64, reason string, authority string, ownerID string) {
	sourceIDs := []string{node.ID}
	for _, evidence := range node.Evidence {
		if evidence.SourceID != "" {
			sourceIDs = append(sourceIDs, evidence.SourceID)
		}
	}
	b.records = append(b.records, CandidateRecord{
		ID:            node.ID,
		Kind:          "leaf",
		Role:          node.Role,
		SourceIDs:     uniqueStrings(sourceIDs),
		BBox:          node.SourceBBox,
		Confidence:    firstConfidence(node),
		Decision:      decision,
		Score:         round3(score),
		Reason:        reason,
		BBoxAuthority: authority,
		OwnerID:       ownerID,
	})
}

func (b *builder) recordDetector(item detector.Candidate, decision string, score float64, reason string, authority string, ownerID string) {
	b.records = append(b.records, CandidateRecord{
		ID:            item.ID,
		Kind:          "detector",
		Role:          ir.Role(item.Role),
		SourceIDs:     []string{item.ID},
		BBox:          bboxFromDetector(item.BBox),
		Confidence:    item.Confidence,
		Decision:      decision,
		Score:         round3(score),
		Reason:        reason,
		BBoxAuthority: authority,
		OwnerID:       ownerID,
		PassID:        item.Source.PassID,
		RawLabel:      item.RawLabel,
	})
}

func detectorImageCandidateAccepted(item detector.Candidate) bool {
	box := bboxFromDetector(item.BBox)
	return item.Confidence >= 0.62 && box.Width >= 4 && box.Height >= 4 && area(box) >= 24
}

func isRegionHint(role detector.Role) bool {
	switch role {
	case detector.RoleStatusBar, detector.RoleActionBar, detector.RoleBottomNavigation, detector.RoleListView, detector.RoleViewGroup:
		return true
	default:
		return false
	}
}

func containedByLargeImageOwner(node ir.Node, owners []ir.Node) (ir.Node, bool) {
	for _, owner := range owners {
		if owner.ID == node.ID || owner.Role != ir.RoleImageView {
			continue
		}
		if area(owner.SourceBBox) < max(1, area(node.SourceBBox))*4 {
			continue
		}
		if overlapRatio(node.SourceBBox, owner.SourceBBox) >= 0.75 || centerInside(owner.SourceBBox, node.SourceBBox, 3) {
			return owner, true
		}
	}
	return ir.Node{}, false
}

func textOwnedByImage(text ir.Node, owners []ir.Node) (ir.Node, bool) {
	if text.Role != ir.RoleTextView || area(text.SourceBBox) <= 0 {
		return ir.Node{}, false
	}
	for _, owner := range owners {
		if owner.Role != ir.RoleImageView || area(owner.SourceBBox) < area(text.SourceBBox)*8 {
			continue
		}
		if overlapRatio(text.SourceBBox, owner.SourceBBox) < 0.86 {
			continue
		}
		if float64(area(text.SourceBBox))/float64(max(1, area(owner.SourceBBox))) > 0.12 {
			continue
		}
		return owner, true
	}
	return ir.Node{}, false
}

func controlEligibleBackground(node ir.Node, root ir.BBox) bool {
	box := node.SourceBBox
	if box.Width < 24 || box.Height < 18 || area(box) < 480 {
		return false
	}
	if box.Height > 100 {
		return false
	}
	if root.Width > 0 && box.Width > int(float64(root.Width)*0.94) {
		return false
	}
	kind := firstEvidenceKind(node)
	if kind == "control_surface_background" || kind == "rounded_background" {
		return true
	}
	if kind == "solid_background" && box.Height <= 70 {
		return true
	}
	return strings.Contains(kind, "control")
}

func topRegionBackground(box ir.BBox, root ir.BBox) bool {
	return root.Width > 0 && box.Y <= 4 && box.Width >= int(float64(root.Width)*0.80) && box.Height >= 24 && box.Height <= max(180, root.Height/5)
}

func bottomRegionBackground(box ir.BBox, root ir.BBox) bool {
	if root.Width <= 0 || root.Height <= 0 {
		return false
	}
	return box.Y >= int(float64(root.Height)*0.86) && box.Width >= int(float64(root.Width)*0.65) && box.Height >= 18
}

func bboxFromDetector(box detector.BBox) ir.BBox {
	return ir.BBox{
		X:      int(math.Round(box.X)),
		Y:      int(math.Round(box.Y)),
		Width:  max(0, int(math.Round(box.Width))),
		Height: max(0, int(math.Round(box.Height))),
	}
}

func graphNode(node ir.Node, decision string, score float64, reason string, authority string, sourceIDs []string) OwnershipNode {
	return OwnershipNode{
		ID:            node.ID,
		Role:          node.Role,
		BBox:          node.SourceBBox,
		Decision:      decision,
		Reason:        reason,
		Score:         round3(score),
		BBoxAuthority: authority,
		SourceIDs:     uniqueStrings(sourceIDs),
	}
}

func detectorNotes(item detector.Candidate) string {
	parts := []string{"pass=" + item.Source.PassID}
	if item.RawLabel != "" {
		parts = append(parts, "label="+item.RawLabel)
	}
	if item.Source.Reason != "" {
		parts = append(parts, "reason="+item.Source.Reason)
	}
	return strings.Join(parts, "/")
}

func firstEvidenceKind(node ir.Node) string {
	if len(node.Evidence) == 0 {
		return ""
	}
	return node.Evidence[0].Kind
}

func firstConfidence(node ir.Node) float64 {
	for _, item := range node.Evidence {
		if item.Confidence > 0 {
			return item.Confidence
		}
	}
	return 0
}

func uniqueStrings(values []string) []string {
	seen := map[string]bool{}
	out := []string{}
	for _, value := range values {
		value = strings.TrimSpace(value)
		if value == "" || seen[value] {
			continue
		}
		seen[value] = true
		out = append(out, value)
	}
	sort.Strings(out)
	return out
}

func sortNodes(nodes []ir.Node) {
	sort.SliceStable(nodes, func(i, j int) bool {
		a, c := nodes[i].SourceBBox, nodes[j].SourceBBox
		if a.Y != c.Y {
			return a.Y < c.Y
		}
		if a.X != c.X {
			return a.X < c.X
		}
		return nodes[i].ID < nodes[j].ID
	})
}

func assignSequences(root *ir.Node) {
	seq := 0
	var walk func(*ir.Node)
	walk = func(node *ir.Node) {
		node.Seq = seq
		node.HasSeq = true
		node.SchemaID = schemaID(node.Role, node.SourceBBox, seq)
		seq++
		for i := len(node.Children) - 1; i >= 0; i-- {
			walk(&node.Children[i])
		}
	}
	walk(root)
}

func summarize(root ir.Node) ir.Summary {
	summary := ir.Summary{
		RoleCounts:      map[string]int{},
		FigmaTypeCounts: map[string]int{},
	}
	var walk func(ir.Node, int)
	walk = func(node ir.Node, depth int) {
		summary.NodeCount++
		if depth > summary.MaxDepth {
			summary.MaxDepth = depth
		}
		summary.RoleCounts[string(node.Role)]++
		summary.FigmaTypeCounts[string(node.FigmaType)]++
		for _, child := range node.Children {
			walk(child, depth+1)
		}
	}
	walk(root, 0)
	return summary
}

func schemaID(role ir.Role, box ir.BBox, seq int) string {
	if role == ir.RoleRoot {
		return "root_0"
	}
	return fmt.Sprintf("%s_%d_%d_%d", role, box.X, box.Y, seq)
}

func centerInside(parent, child ir.BBox, tolerance int) bool {
	cx := child.X + child.Width/2
	cy := child.Y + child.Height/2
	return parent.X-tolerance <= cx &&
		parent.Y-tolerance <= cy &&
		parent.X+parent.Width+tolerance >= cx &&
		parent.Y+parent.Height+tolerance >= cy
}

func overlapRatio(a, b ir.BBox) float64 {
	intersection := intersectionArea(a, b)
	if intersection <= 0 {
		return 0
	}
	return float64(intersection) / float64(max(1, area(a)))
}

func iou(a ir.BBox, b ir.BBox) float64 {
	intersection := intersectionArea(a, b)
	if intersection <= 0 {
		return 0
	}
	union := area(a) + area(b) - intersection
	return float64(intersection) / float64(max(1, union))
}

func intersectionArea(a, b ir.BBox) int {
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

func round3(value float64) float64 {
	return math.Round(value*1000) / 1000
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}

func max(a, b int) int {
	if a > b {
		return a
	}
	return b
}
