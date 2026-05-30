package control

import (
	"encoding/json"
	"fmt"
	"os"
	"sort"
	"strings"
	"unicode"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/ir"
)

const ArtifactName = "codia_control_ir.v1.json"
const StageArtifactName = "codia_control_stage.v1.json"

type Options struct {
	InputPath string
}

type Result struct {
	SchemaName     string       `json:"schemaName"`
	Version        string       `json:"version"`
	Source         ir.Source    `json:"source"`
	RootBBox       ir.BBox      `json:"rootBBox"`
	Controls       []ir.Node    `json:"controls"`
	Remaining      []ir.Node    `json:"remaining"`
	Rejections     []Diagnostic `json:"rejections,omitempty"`
	Diagnostics    Diagnostics  `json:"diagnostics"`
	SourceDocument ir.Document  `json:"-"`
}

type Diagnostic struct {
	BackgroundID  string   `json:"backgroundId,omitempty"`
	ForegroundIDs []string `json:"foregroundIds,omitempty"`
	Reason        string   `json:"reason"`
	BBox          ir.BBox  `json:"bbox"`
	EvidenceKind  string   `json:"evidenceKind,omitempty"`
}

type Diagnostics struct {
	InputNodeCount int            `json:"inputNodeCount"`
	CandidateCount int            `json:"candidateCount"`
	ControlCount   int            `json:"controlCount"`
	RemainingCount int            `json:"remainingCount"`
	RejectedCount  int            `json:"rejectedCount"`
	ControlRoles   map[string]int `json:"controlRoles,omitempty"`
}

type synthesisCandidate struct {
	BackgroundIndex int
	Foreground      []int
	Suppressed      []int
	Role            ir.Role
	BBox            ir.BBox
}

func Compile(options Options) (Result, error) {
	if options.InputPath == "" {
		return Result{}, fmt.Errorf("missing input path")
	}
	doc, err := readIR(options.InputPath)
	if err != nil {
		return Result{}, err
	}
	out, err := Synthesize(doc)
	if err != nil {
		return Result{}, err
	}
	out.Source.InputPath = options.InputPath
	out.SourceDocument.Source.InputPath = options.InputPath
	return out, nil
}

func Synthesize(doc ir.Document) (Result, error) {
	if doc.SchemaName != ir.SchemaName {
		return Result{}, fmt.Errorf("expected %s, got %q", ir.SchemaName, doc.SchemaName)
	}
	root := doc.Root
	candidates, rejections := buildCandidates(root.Children, root.SourceBBox)
	used := map[int]bool{}
	var controls []ir.Node
	for _, candidate := range candidates {
		if used[candidate.BackgroundIndex] || anyUsed(candidate.Foreground, used) {
			rejections = append(rejections, diagnosticForCandidate(candidate, root.Children, "overlapping_candidate_consumed"))
			continue
		}
		controlNode := makeControlNode(len(controls)+1, candidate, root.Children)
		controls = append(controls, controlNode)
		used[candidate.BackgroundIndex] = true
		for _, index := range candidate.Foreground {
			used[index] = true
		}
		for _, index := range candidate.Suppressed {
			used[index] = true
		}
		markContainedBackgroundsUsed(candidate, root.Children, used)
	}
	var remaining []ir.Node
	for i, child := range root.Children {
		if used[i] {
			continue
		}
		remaining = append(remaining, child)
	}
	result := Result{
		SchemaName:     "CodiaControlStage",
		Version:        "1.0",
		Source:         doc.Source,
		RootBBox:       root.SourceBBox,
		Controls:       controls,
		Remaining:      remaining,
		Rejections:     rejections,
		SourceDocument: doc,
	}
	result.Diagnostics = buildDiagnostics(root.Children, candidates, controls, remaining, rejections)
	return result, nil
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

func ToDocument(result Result) ir.Document {
	root := result.SourceDocument.Root
	if root.ID == "" {
		root = ir.Node{
			ID:          "root_0",
			Role:        ir.RoleRoot,
			SourceBBox:  result.RootBBox,
			FigmaBBox:   result.RootBBox,
			FigmaType:   ir.FigmaFrame,
			VisibleName: "Root",
			Style:       ir.Style{Visible: true, Opacity: 1},
		}
	}
	root.Children = nil
	root.Children = append(root.Children, result.Controls...)
	root.Children = append(root.Children, result.Remaining...)
	assignSequences(&root)
	out := result.SourceDocument
	if out.SchemaName == "" {
		out.SchemaName = ir.SchemaName
		out.Version = ir.Version
	}
	out.Source = result.Source
	out.Root = root
	out.Summary = summarize(root)
	return out
}

func buildCandidates(nodes []ir.Node, rootBBox ir.BBox) ([]synthesisCandidate, []Diagnostic) {
	var candidates []synthesisCandidate
	var rejections []Diagnostic
	for i := range nodes {
		background := nodes[i]
		if reason := controlBackgroundRejection(background, rootBBox); reason != "" {
			if background.Role == ir.RoleBackground {
				rejections = append(rejections, diagnosticForBackground(background, reason))
			}
			continue
		}
		foreground, suppressed := containedForeground(nodes, i)
		role, ok, reason := classifyControl(background, foreground, nodes)
		if !ok {
			if reason == "" {
				reason = "foreground_not_control_like"
			}
			rejections = append(rejections, diagnosticForForeground(background, foreground, nodes, reason))
			continue
		}
		candidates = append(candidates, synthesisCandidate{
			BackgroundIndex: i,
			Foreground:      foreground,
			Suppressed:      suppressed,
			Role:            role,
			BBox:            unionCandidateBBox(background, foreground, nodes),
		})
	}
	sort.SliceStable(candidates, func(i, j int) bool {
		if candidates[i].Role != candidates[j].Role {
			return candidates[i].Role == ir.RoleEditText
		}
		iAction, jAction := wideActionCandidate(candidates[i], nodes), wideActionCandidate(candidates[j], nodes)
		if iAction != jAction {
			return iAction
		}
		ai, aj := area(candidates[i].BBox), area(candidates[j].BBox)
		if iAction && jAction && ai != aj {
			return ai > aj
		}
		if ai != aj {
			return ai < aj
		}
		if candidates[i].BBox.Y != candidates[j].BBox.Y {
			return candidates[i].BBox.Y < candidates[j].BBox.Y
		}
		return candidates[i].BBox.X < candidates[j].BBox.X
	})
	return candidates, rejections
}

func markContainedBackgroundsUsed(candidate synthesisCandidate, nodes []ir.Node, used map[int]bool) {
	for i, node := range nodes {
		if used[i] || i == candidate.BackgroundIndex || node.Role != ir.RoleBackground {
			continue
		}
		if containsBBox(candidate.BBox, node.SourceBBox, 2) {
			used[i] = true
		}
	}
}

func wideActionCandidate(candidate synthesisCandidate, nodes []ir.Node) bool {
	if candidate.Role != ir.RoleButton || candidate.BBox.Width < 240 {
		return false
	}
	textWidth := 0
	for _, index := range candidate.Foreground {
		if nodes[index].Role == ir.RoleTextView {
			textWidth += nodes[index].SourceBBox.Width
		}
	}
	return textWidth >= 120
}

func controlBackgroundRejection(node ir.Node, rootBBox ir.BBox) string {
	if node.Role != ir.RoleBackground {
		return "not_background"
	}
	box := node.SourceBBox
	if box.Width < 24 || box.Height < 18 || area(box) < 480 {
		return "background_too_small"
	}
	if box.Height > 90 {
		return "background_too_tall"
	}
	if rootBBox.Width > 0 && box.Width > int(float64(rootBBox.Width)*0.92) {
		return "background_too_wide_for_control"
	}
	if evidenceKind(node) == "" {
		return "missing_background_evidence"
	}
	return ""
}

func containedForeground(nodes []ir.Node, backgroundIndex int) ([]int, []int) {
	background := nodes[backgroundIndex]
	var out []int
	var suppressed []int
	for i := range nodes {
		if i == backgroundIndex {
			continue
		}
		node := nodes[i]
		if node.Role != ir.RoleTextView && node.Role != ir.RoleImageView {
			continue
		}
		if node.Role == ir.RoleImageView && nearSameBBox(background.SourceBBox, node.SourceBBox) {
			continue
		}
		if node.Role == ir.RoleImageView && area(node.SourceBBox) > area(background.SourceBBox)/2 {
			continue
		}
		if centerInside(background.SourceBBox, node.SourceBBox, 4) || intersectionRatio(node.SourceBBox, background.SourceBBox) >= 0.55 {
			if node.Role == ir.RoleImageView && rejectControlImageFragment(background.SourceBBox, node.SourceBBox) {
				suppressed = append(suppressed, i)
				continue
			}
			out = append(out, i)
		}
	}
	sort.SliceStable(out, func(i, j int) bool {
		a, b := nodes[out[i]].SourceBBox, nodes[out[j]].SourceBBox
		if a.Y != b.Y {
			return a.Y < b.Y
		}
		return a.X < b.X
	})
	sort.Ints(suppressed)
	return out, suppressed
}

func rejectControlImageFragment(background ir.BBox, image ir.BBox) bool {
	if area(image) <= 0 || area(background) <= 0 {
		return true
	}
	if area(image) < 120 {
		return true
	}
	if background.Width >= 120 && area(image) < 260 {
		return true
	}
	if edgeHeightFragment(background, image) {
		return true
	}
	if edgeSmallFragment(background, image) {
		return true
	}
	return false
}

func edgeHeightFragment(background ir.BBox, image ir.BBox) bool {
	if background.Width < 90 || background.Height < 24 {
		return false
	}
	if image.Width > max(24, background.Width/5) {
		return false
	}
	if image.Height < int(float64(background.Height)*0.72) {
		return false
	}
	if image.Height > background.Height+6 {
		return false
	}
	touchesLeft := abs(image.X-background.X) <= 3
	touchesRight := abs(image.X+image.Width-(background.X+background.Width)) <= 3
	if !touchesLeft && !touchesRight {
		return false
	}
	return true
}

func edgeSmallFragment(background ir.BBox, image ir.BBox) bool {
	if background.Width < 90 || background.Height < 24 {
		return false
	}
	touchesLeft := abs(image.X-background.X) <= 3
	touchesRight := abs(image.X+image.Width-(background.X+background.Width)) <= 3
	if !touchesLeft && !touchesRight {
		return false
	}
	if image.Width > max(32, background.Width/8) {
		return false
	}
	if image.Height > max(28, int(float64(background.Height)*0.55)) {
		return false
	}
	return true
}

func classifyControl(background ir.Node, foreground []int, nodes []ir.Node) (ir.Role, bool, string) {
	if !controlForegroundFits(background, foreground, nodes) {
		return "", false, "foreground_not_control_like"
	}
	if editTextLikeForeground(background, foreground, nodes) {
		return ir.RoleEditText, true, ""
	}
	textCount := 0
	imageCount := 0
	allTextNumeric := true
	allTextPriceLike := true
	for _, index := range foreground {
		node := nodes[index]
		if node.Role == ir.RoleTextView {
			textCount++
			if !numericLikeText(node.VisibleName) {
				allTextNumeric = false
			}
			if !priceLikeText(node.VisibleName) {
				allTextPriceLike = false
			}
		}
		if node.Role == ir.RoleImageView {
			imageCount++
		}
	}
	if contentPanelLikeButton(background, foreground, nodes, textCount) {
		return "", false, "foreground_content_panel_like"
	}
	if textCount > 0 && imageCount == 0 && allTextPriceLike {
		return "", false, "foreground_price_like_label"
	}
	if textCount == 1 && imageCount == 0 && textOnlyNearFillSurface(background, foreground, nodes) {
		return "", false, "foreground_text_near_fill_surface"
	}
	if textCount == 1 && imageCount == 0 && compactTextOnlyLabel(background, foreground, nodes) {
		return "", false, "foreground_compact_text_label"
	}
	if textCount > 0 && !allTextNumeric {
		return ir.RoleButton, true, ""
	}
	if textCount == 0 && imageCount > 0 && background.SourceBBox.Width >= 120 && background.SourceBBox.Height >= 32 {
		return ir.RoleEditText, true, ""
	}
	return "", false, "foreground_not_control_like"
}

func contentPanelLikeButton(background ir.Node, foreground []int, nodes []ir.Node, textCount int) bool {
	box := background.SourceBBox
	if box.Height < 50 || wideActionLike(box, foreground, nodes) {
		return false
	}
	if box.Height >= 70 && textCount >= 2 {
		return true
	}
	foregroundBox, ok := foregroundUnionBBox(foreground, nodes)
	if !ok {
		return false
	}
	foregroundHeightRatio := float64(foregroundBox.Height) / float64(max(1, box.Height))
	centerDelta := abs(centerY(foregroundBox) - centerY(box))
	minDelta := max(10, int(float64(box.Height)*0.18))
	return foregroundHeightRatio <= 0.62 && centerDelta >= minDelta
}

func wideActionLike(box ir.BBox, foreground []int, nodes []ir.Node) bool {
	if box.Width < 240 {
		return false
	}
	textWidth := 0
	for _, index := range foreground {
		if nodes[index].Role == ir.RoleTextView {
			textWidth += nodes[index].SourceBBox.Width
		}
	}
	return textWidth >= 120
}

func textOnlyNearFillSurface(background ir.Node, foreground []int, nodes []ir.Node) bool {
	if len(foreground) != 1 {
		return false
	}
	text := nodes[foreground[0]]
	if text.Role != ir.RoleTextView {
		return false
	}
	box := background.SourceBBox
	fg := text.SourceBBox
	if box.Height < 34 || wideActionLike(box, foreground, nodes) {
		return false
	}
	if urlLikeText(text.VisibleName) {
		return false
	}
	widthRatio := float64(fg.Width) / float64(max(1, box.Width))
	heightRatio := float64(fg.Height) / float64(max(1, box.Height))
	leftPad := fg.X - box.X
	rightPad := box.X + box.Width - (fg.X + fg.Width)
	topPad := fg.Y - box.Y
	bottomPad := box.Y + box.Height - (fg.Y + fg.Height)
	return widthRatio >= 0.86 &&
		heightRatio >= 0.72 &&
		min(leftPad, rightPad) <= 2 &&
		min(topPad, bottomPad) <= 3
}

func compactTextOnlyLabel(background ir.Node, foreground []int, nodes []ir.Node) bool {
	if len(foreground) != 1 {
		return false
	}
	text := nodes[foreground[0]]
	if text.Role != ir.RoleTextView {
		return false
	}
	box := background.SourceBBox
	return box.Width <= 72 && box.Height <= 40 && len([]rune(strings.TrimSpace(text.VisibleName))) <= 4
}

func editTextLikeForeground(background ir.Node, foreground []int, nodes []ir.Node) bool {
	box := background.SourceBBox
	if box.Width < 160 || box.Height < 32 {
		return false
	}
	totalWidth := 0
	totalArea := 0
	for _, index := range foreground {
		fg := nodes[index].SourceBBox
		totalWidth += fg.Width
		totalArea += area(fg)
	}
	if totalWidth == 0 {
		return false
	}
	return float64(totalWidth)/float64(max(1, box.Width)) <= 0.28 &&
		float64(totalArea)/float64(max(1, area(box))) <= 0.18
}

func controlForegroundFits(background ir.Node, foreground []int, nodes []ir.Node) bool {
	if len(foreground) == 0 {
		return false
	}
	box := background.SourceBBox
	for _, index := range foreground {
		node := nodes[index]
		fg := node.SourceBBox
		if fg.X < box.X-4 || fg.Y < box.Y-4 ||
			fg.X+fg.Width > box.X+box.Width+4 ||
			fg.Y+fg.Height > box.Y+box.Height+4 {
			return false
		}
		if node.Role == ir.RoleTextView {
			if intersectionRatio(fg, box) < 0.72 && !centerInside(box, fg, 2) {
				return false
			}
		}
	}
	return true
}

func makeControlNode(index int, candidate synthesisCandidate, source []ir.Node) ir.Node {
	role := candidate.Role
	id := fmt.Sprintf("control_%04d", index)
	control := ir.Node{
		ID:          id,
		Role:        role,
		SourceBBox:  candidate.BBox,
		FigmaBBox:   candidate.BBox,
		FigmaType:   ir.FigmaFrame,
		VisibleName: controlVisibleName(role),
		SourcePath:  id,
		Evidence: []ir.Evidence{{
			Kind:       controlEvidenceKind(role),
			BBox:       candidate.BBox,
			Confidence: 0.72,
			SourceID:   source[candidate.BackgroundIndex].ID,
			Notes:      evidenceKind(source[candidate.BackgroundIndex]),
		}},
		Style: ir.Style{Visible: true, Opacity: 1},
	}
	for _, foregroundIndex := range candidate.Foreground {
		control.Children = append(control.Children, source[foregroundIndex])
	}
	background := source[candidate.BackgroundIndex]
	if role == ir.RoleButton {
		background.Role = ir.RoleBgButton
	} else {
		background.Role = ir.RoleBgEditText
	}
	background.ID = id + "_bg"
	background.VisibleName = "Background"
	background.FigmaType = ir.FigmaRoundedRectangle
	background.SourcePath = source[candidate.BackgroundIndex].ID
	control.Children = append(control.Children, background)
	return control
}

func unionCandidateBBox(background ir.Node, foreground []int, nodes []ir.Node) ir.BBox {
	box := background.SourceBBox
	for _, index := range foreground {
		box = unionBBox(box, nodes[index].SourceBBox)
	}
	return box
}

func controlVisibleName(role ir.Role) string {
	if role == ir.RoleEditText {
		return "Text"
	}
	return "Button"
}

func controlEvidenceKind(role ir.Role) string {
	if role == ir.RoleEditText {
		return "control_edit_text"
	}
	return "control_button"
}

func evidenceKind(node ir.Node) string {
	if len(node.Evidence) == 0 {
		return ""
	}
	return node.Evidence[0].Kind
}

func diagnosticForBackground(node ir.Node, reason string) Diagnostic {
	return Diagnostic{
		BackgroundID: node.ID,
		Reason:       reason,
		BBox:         node.SourceBBox,
		EvidenceKind: evidenceKind(node),
	}
}

func diagnosticForForeground(background ir.Node, foreground []int, nodes []ir.Node, reason string) Diagnostic {
	return Diagnostic{
		BackgroundID:  background.ID,
		ForegroundIDs: foregroundIDs(foreground, nodes),
		Reason:        reason,
		BBox:          background.SourceBBox,
		EvidenceKind:  evidenceKind(background),
	}
}

func diagnosticForCandidate(candidate synthesisCandidate, nodes []ir.Node, reason string) Diagnostic {
	background := nodes[candidate.BackgroundIndex]
	return Diagnostic{
		BackgroundID:  background.ID,
		ForegroundIDs: foregroundIDs(candidate.Foreground, nodes),
		Reason:        reason,
		BBox:          candidate.BBox,
		EvidenceKind:  evidenceKind(background),
	}
}

func foregroundIDs(indices []int, nodes []ir.Node) []string {
	out := make([]string, 0, len(indices))
	for _, index := range indices {
		if index >= 0 && index < len(nodes) {
			out = append(out, nodes[index].ID)
		}
	}
	return out
}

func buildDiagnostics(input []ir.Node, candidates []synthesisCandidate, controls []ir.Node, remaining []ir.Node, rejections []Diagnostic) Diagnostics {
	out := Diagnostics{
		InputNodeCount: len(input),
		CandidateCount: len(candidates),
		ControlCount:   len(controls),
		RemainingCount: len(remaining),
		RejectedCount:  len(rejections),
		ControlRoles:   map[string]int{},
	}
	for _, control := range controls {
		out.ControlRoles[string(control.Role)]++
	}
	if len(out.ControlRoles) == 0 {
		out.ControlRoles = nil
	}
	return out
}

func numericLikeText(value string) bool {
	value = strings.TrimSpace(value)
	if value == "" {
		return true
	}
	runes := []rune(value)
	if len(runes) > 2 {
		return false
	}
	for _, r := range runes {
		if !unicode.IsDigit(r) {
			return false
		}
	}
	return true
}

func priceLikeText(value string) bool {
	value = strings.TrimSpace(value)
	if value == "" {
		return false
	}
	hasDigit := false
	for _, r := range value {
		if unicode.IsDigit(r) {
			hasDigit = true
			continue
		}
		switch r {
		case '￥', '$', '.', ',', '/', '／', '-', '+', '元', '天', '¥':
			continue
		default:
			return false
		}
	}
	return hasDigit
}

func urlLikeText(value string) bool {
	value = strings.TrimSpace(value)
	if len([]rune(value)) < 4 || !strings.Contains(value, ".") {
		return false
	}
	hasLetter := false
	for _, r := range value {
		if unicode.IsSpace(r) {
			return false
		}
		if unicode.IsLetter(r) {
			hasLetter = true
		}
	}
	return hasLetter
}

func anyUsed(indices []int, used map[int]bool) bool {
	for _, index := range indices {
		if used[index] {
			return true
		}
	}
	return false
}

func sortNodes(nodes []ir.Node) {
	sort.SliceStable(nodes, func(i, j int) bool {
		a, b := nodes[i].SourceBBox, nodes[j].SourceBBox
		if a.Y != b.Y {
			return a.Y < b.Y
		}
		if a.X != b.X {
			return a.X < b.X
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

func containsBBox(parent, child ir.BBox, tolerance int) bool {
	return parent.X-tolerance <= child.X &&
		parent.Y-tolerance <= child.Y &&
		parent.X+parent.Width+tolerance >= child.X+child.Width &&
		parent.Y+parent.Height+tolerance >= child.Y+child.Height
}

func nearSameBBox(a, b ir.BBox) bool {
	return abs(a.X-b.X) <= 3 &&
		abs(a.Y-b.Y) <= 3 &&
		abs(a.Width-b.Width) <= 6 &&
		abs(a.Height-b.Height) <= 6
}

func intersectionRatio(a, b ir.BBox) float64 {
	intersection := intersectionArea(a, b)
	if intersection <= 0 {
		return 0
	}
	return float64(intersection) / float64(max(1, area(a)))
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

func unionBBox(a, b ir.BBox) ir.BBox {
	x1 := min(a.X, b.X)
	y1 := min(a.Y, b.Y)
	x2 := max(a.X+a.Width, b.X+b.Width)
	y2 := max(a.Y+a.Height, b.Y+b.Height)
	return ir.BBox{X: x1, Y: y1, Width: x2 - x1, Height: y2 - y1}
}

func foregroundUnionBBox(indices []int, nodes []ir.Node) (ir.BBox, bool) {
	var out ir.BBox
	ok := false
	for _, index := range indices {
		if !ok {
			out = nodes[index].SourceBBox
			ok = true
			continue
		}
		out = unionBBox(out, nodes[index].SourceBBox)
	}
	return out, ok
}

func centerY(box ir.BBox) int {
	return box.Y + box.Height/2
}

func area(box ir.BBox) int {
	return max(0, box.Width) * max(0, box.Height)
}

func abs(value int) int {
	if value < 0 {
		return -value
	}
	return value
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
