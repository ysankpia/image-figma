package tree

import (
	"encoding/json"
	"fmt"
	"os"
	"sort"
	"strings"

	controlstage "github.com/luqing-studio/image-figma/services/backend-go/internal/codia/control"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/ir"
)

const ArtifactName = "codia_tree_ir.v1.json"

type Options struct {
	InputPath string
}

func Compile(options Options) (ir.Document, error) {
	if options.InputPath == "" {
		return ir.Document{}, fmt.Errorf("missing input path")
	}
	doc, err := readIR(options.InputPath)
	if err != nil {
		return ir.Document{}, err
	}
	out, err := Build(doc)
	if err != nil {
		return ir.Document{}, err
	}
	out.Source.InputPath = options.InputPath
	return out, nil
}

func Build(doc ir.Document) (ir.Document, error) {
	if doc.SchemaName != ir.SchemaName {
		return ir.Document{}, fmt.Errorf("expected %s, got %q", ir.SchemaName, doc.SchemaName)
	}
	return buildFromDocument(doc)
}

func BuildFromControl(result controlstage.Result) (ir.Document, error) {
	doc := controlstage.ToDocument(result)
	return buildFromDocument(doc)
}

func buildFromDocument(doc ir.Document) (ir.Document, error) {
	b := builder{
		source:      doc,
		root:        doc.Root.SourceBBox,
		regionHints: regionHintsFromEvidence(doc.Root.Evidence, doc.Root.SourceBBox),
		used:        map[string]bool{},
	}
	outRoot := rootShell(doc.Root)
	hasTopSearch := b.hasTopSearch()
	bottomNav := b.buildBottomNavigation(hasTopSearch)
	rootBackgrounds := b.takeRootLateBackgrounds(bottomNav)

	if hasTopSearch {
		if top := b.buildTopWrapper(); top.ID != "" {
			outRoot.Children = append(outRoot.Children, top)
		}
	}
	if hasTopSearch {
		if sideRail := b.buildSideRail(bottomNav); sideRail.ID != "" {
			outRoot.Children = append(outRoot.Children, sideRail)
		}
	}

	if body := b.buildBody(hasTopSearch, bottomNav); body.ID != "" {
		outRoot.Children = append(outRoot.Children, body)
	}
	if bottomNav.ID != "" {
		outRoot.Children = append(outRoot.Children, bottomNav)
	}
	outRoot.Children = append(outRoot.Children, rootBackgrounds...)
	outRoot.Children = append(outRoot.Children, b.remainingRootChildren()...)
	orderChildren(&outRoot)
	assignSequences(&outRoot)

	out := doc
	out.Root = outRoot
	out.Summary = summarize(outRoot)
	out.Source.DesignFrameName = "Codia compiler tree"
	return out, nil
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
	return doc, nil
}

type builder struct {
	source      ir.Document
	root        ir.BBox
	regionHints []regionHint
	used        map[string]bool
}

type regionHint struct {
	Role       ir.Role
	BBox       ir.BBox
	Confidence float64
	SourceID   string
	Label      string
}

type proposalKind string

const (
	proposalStatusBar        proposalKind = "status_bar_candidate"
	proposalTopWrapper       proposalKind = "top_wrapper_owner"
	proposalTopCategoryList  proposalKind = "top_category_list"
	proposalTopCategoryItem  proposalKind = "top_category_item"
	proposalSearchRow        proposalKind = "search_row_owner"
	proposalActionBar        proposalKind = "action_bar_candidate"
	proposalBottomNav        proposalKind = "bottom_navigation_candidate"
	proposalBottomTab        proposalKind = "bottom_navigation_tab"
	proposalBottomNavWrapper proposalKind = "bottom_navigation_wrapper"
	proposalBodyList         proposalKind = "body_list_owner"
	proposalRepeatedRowList  proposalKind = "repeated_row_list"
	proposalRepeatedRowItem  proposalKind = "repeated_row_item"
	proposalMajorSection     proposalKind = "major_section_owner"
	proposalHintedSlotList   proposalKind = "assembly_region_hint_slot_list"
	proposalHintedSlot       proposalKind = "assembly_region_hint_slot"
	proposalSideRail         proposalKind = "side_rail_candidate"
	proposalSideRailInner    proposalKind = "side_rail_inner_list"
	proposalSideRailStack    proposalKind = "side_rail_stack_owner"
)

func (b *builder) children() []ir.Node {
	return b.source.Root.Children
}

func regionHintsFromEvidence(evidence []ir.Evidence, root ir.BBox) []regionHint {
	var out []regionHint
	for _, item := range evidence {
		if item.Kind != "assembly_region_hint" || item.Confidence <= 0 {
			continue
		}
		role := regionHintRole(item.Notes)
		if !regionHintRoleAllowed(role) {
			continue
		}
		box, ok := clippedRegionHintBox(item.BBox, root)
		if !ok {
			continue
		}
		out = append(out, regionHint{
			Role:       role,
			BBox:       box,
			Confidence: item.Confidence,
			SourceID:   item.SourceID,
			Label:      regionHintLabel(item.Notes),
		})
	}
	sort.SliceStable(out, func(i, j int) bool {
		if out[i].Role != out[j].Role {
			return string(out[i].Role) < string(out[j].Role)
		}
		if out[i].Confidence != out[j].Confidence {
			return out[i].Confidence > out[j].Confidence
		}
		return area(out[i].BBox) < area(out[j].BBox)
	})
	return out
}

func regionHintRole(notes string) ir.Role {
	roleText := strings.TrimSpace(strings.SplitN(notes, "/", 2)[0])
	switch ir.Role(roleText) {
	case ir.RoleStatusBar, ir.RoleActionBar, ir.RoleBottomNavigation, ir.RoleListView, ir.RoleViewGroup, ir.RoleEditText, ir.RoleBackground:
		return ir.Role(roleText)
	default:
		return ""
	}
}

func regionHintRoleAllowed(role ir.Role) bool {
	switch role {
	case ir.RoleStatusBar, ir.RoleActionBar, ir.RoleBottomNavigation, ir.RoleListView, ir.RoleViewGroup, ir.RoleEditText, ir.RoleBackground:
		return true
	default:
		return false
	}
}

func regionHintLabel(notes string) string {
	for _, part := range strings.Split(notes, "/") {
		if label, ok := strings.CutPrefix(part, "label="); ok {
			return label
		}
	}
	return ""
}

func clippedRegionHintBox(box ir.BBox, root ir.BBox) (ir.BBox, bool) {
	if box.Width <= 0 || box.Height <= 0 || root.Width <= 0 || root.Height <= 0 {
		return ir.BBox{}, false
	}
	x1 := max(0, box.X)
	y1 := max(0, box.Y)
	x2 := min(root.Width, bottomX(box))
	y2 := min(root.Height, bottom(box))
	if x2 <= x1 || y2 <= y1 {
		return ir.BBox{}, false
	}
	return ir.BBox{X: x1, Y: y1, Width: x2 - x1, Height: y2 - y1}, true
}

func (b *builder) bestRegionHint(role ir.Role, minConfidence float64) (regionHint, bool) {
	var best regionHint
	for _, hint := range b.regionHints {
		if hint.Role != role || hint.Confidence < minConfidence {
			continue
		}
		if best.Role == "" || hint.Confidence > best.Confidence ||
			(hint.Confidence == best.Confidence && area(hint.BBox) > area(best.BBox)) {
			best = hint
		}
	}
	return best, best.Role != ""
}

func (b *builder) orderedRegionHints(roles map[ir.Role]bool, minConfidence float64) []regionHint {
	var out []regionHint
	for _, hint := range b.regionHints {
		if !roles[hint.Role] || hint.Confidence < minConfidence {
			continue
		}
		out = append(out, hint)
	}
	sort.SliceStable(out, func(i, j int) bool {
		if area(out[i].BBox) != area(out[j].BBox) {
			return area(out[i].BBox) < area(out[j].BBox)
		}
		if out[i].BBox.Y != out[j].BBox.Y {
			return out[i].BBox.Y < out[j].BBox.Y
		}
		if out[i].BBox.X != out[j].BBox.X {
			return out[i].BBox.X < out[j].BBox.X
		}
		return out[i].SourceID < out[j].SourceID
	})
	return out
}

func rootShell(root ir.Node) ir.Node {
	root.Children = nil
	root.Role = ir.RoleRoot
	root.FigmaType = ir.FigmaFrame
	root.VisibleName = "Root"
	root.Style.Visible = true
	if root.Style.Opacity == 0 {
		root.Style.Opacity = 1
	}
	if root.SourceBBox.Width == 0 || root.SourceBBox.Height == 0 {
		root.SourceBBox = root.FigmaBBox
	}
	if root.FigmaBBox.Width == 0 || root.FigmaBBox.Height == 0 {
		root.FigmaBBox = root.SourceBBox
	}
	return root
}

func (b *builder) hasTopSearch() bool {
	for _, node := range b.children() {
		if node.Role == ir.RoleEditText && node.SourceBBox.Y < max(180, b.root.Height/6) {
			return true
		}
	}
	return false
}

func (b *builder) buildTopWrapper() ir.Node {
	statusBox := ir.BBox{X: 0, Y: 0, Width: b.root.Width, Height: topStatusHeight(b.root)}
	var statusHint *regionHint
	if hint, ok := b.bestRegionHint(ir.RoleStatusBar, 0.80); ok && plausibleTopRegionHint(hint.BBox, b.root) {
		statusBox = hint.BBox
		statusHint = &hint
	}
	status := b.makeContainer("tree_status_0001", ir.RoleStatusBar, statusBox, proposalStatusBar)
	if statusHint != nil {
		applyRegionHintEvidence(&status, *statusHint)
	}
	for _, node := range b.children() {
		if b.isUsed(node) || discardPhysicalNoise(node) || !topChromeNode(node, status.SourceBBox) {
			continue
		}
		status.Children = append(status.Children, node)
		b.mark(node)
	}
	orderChildren(&status)

	category := b.buildTopCategoryList()
	search := b.buildSearchRow()
	topHeight := max(236, bottom(status.SourceBBox))
	for _, child := range []ir.Node{category, search} {
		if child.ID != "" {
			topHeight = max(topHeight, bottom(child.SourceBBox))
		}
	}
	top := b.makeContainer("tree_top_0001", ir.RoleViewGroup, ir.BBox{X: 0, Y: 0, Width: b.root.Width, Height: min(topHeight, max(1, b.root.Height/3))}, proposalTopWrapper)
	if len(status.Children) > 0 {
		top.Children = append(top.Children, status)
	}
	if category.ID != "" {
		top.Children = append(top.Children, category)
	}
	if search.ID != "" {
		top.Children = append(top.Children, search)
	}
	top.Children = append(top.Children, b.takeOrMakeBackground("tree_top_bg_0001", top.SourceBBox, "top_region_background"))
	orderChildren(&top)
	return top
}

func (b *builder) buildTopCategoryList() ir.Node {
	band := ir.BBox{X: 0, Y: topStatusHeight(b.root), Width: b.root.Width, Height: 86}
	var items []ir.Node
	for _, node := range b.children() {
		if b.isUsed(node) || discardPhysicalNoise(node) || node.Role != ir.RoleTextView {
			continue
		}
		if centerInside(band, node.SourceBBox) {
			items = append(items, node)
		}
	}
	if len(items) < 3 {
		return ir.Node{}
	}
	sortNodes(items)
	listBox := ir.BBox{X: 0, Y: band.Y, Width: max(1, b.root.Width-35), Height: 76}
	list := b.makeContainer("tree_top_categories_0001", ir.RoleListView, listBox, proposalTopCategoryList)
	for i, item := range items {
		if edgeRailItem(item.SourceBBox, b.root) {
			list.Children = append(list.Children, item)
			b.mark(item)
			continue
		}
		groupBox := padBBox(item.SourceBBox, 16, 8, b.root)
		groupBox.Y = min(groupBox.Y, listBox.Y+14)
		groupBox.Height = max(groupBox.Height, min(76, listBox.Height))
		group := b.makeContainer(fmt.Sprintf("tree_top_category_%04d", i+1), ir.RoleViewGroup, groupBox, proposalTopCategoryItem)
		group.Children = append(group.Children, item)
		b.mark(item)
		orderChildren(&group)
		list.Children = append(list.Children, group)
	}
	for _, node := range b.children() {
		if b.isUsed(node) || discardPhysicalNoise(node) || node.Role != ir.RoleImageView {
			continue
		}
		if centerInside(listBox, node.SourceBBox) {
			list.Children = append(list.Children, node)
			b.mark(node)
		}
	}
	orderChildren(&list)
	return list
}

func (b *builder) buildSearchRow() ir.Node {
	var items []ir.Node
	for _, node := range b.children() {
		if b.isUsed(node) || discardPhysicalNoise(node) {
			continue
		}
		if node.SourceBBox.Y >= 135 && node.SourceBBox.Y < 235 &&
			(node.Role == ir.RoleEditText || node.Role == ir.RoleButton || smallChromeLeaf(node)) {
			items = append(items, node)
		}
	}
	if len(items) == 0 {
		return ir.Node{}
	}
	row := b.makeContainer("tree_search_row_0001", ir.RoleViewGroup, ir.BBox{X: 0, Y: 149, Width: b.root.Width, Height: 79}, proposalSearchRow)
	for _, item := range items {
		row.Children = append(row.Children, item)
		b.mark(item)
	}
	orderChildren(&row)
	return row
}

func (b *builder) buildActionBar() ir.Node {
	box := ir.BBox{X: 0, Y: 0, Width: b.root.Width, Height: 74}
	var actionHint *regionHint
	if hint, ok := b.bestRegionHint(ir.RoleActionBar, 0.80); ok && plausibleTopRegionHint(hint.BBox, b.root) {
		box = hint.BBox
		actionHint = &hint
	}
	action := b.makeContainer("tree_actionbar_0001", ir.RoleActionBar, box, proposalActionBar)
	if actionHint != nil {
		applyRegionHintEvidence(&action, *actionHint)
	}
	for _, node := range b.children() {
		if b.isUsed(node) || discardPhysicalNoise(node) || !topChromeNode(node, box) {
			continue
		}
		action.Children = append(action.Children, node)
		b.mark(node)
	}
	if len(action.Children) == 0 {
		return ir.Node{}
	}
	orderChildren(&action)
	return action
}

func (b *builder) buildBottomNavigation(wrapTabs bool) ir.Node {
	navHeight := clamp(int(float64(max(1, b.root.Height))*0.108), 96, min(156, max(96, b.root.Height)))
	navY := max(0, b.root.Height-navHeight)
	navBox := ir.BBox{X: 0, Y: navY, Width: b.root.Width, Height: b.root.Height - navY}
	var navHint *regionHint
	if hint, ok := b.bestRegionHint(ir.RoleBottomNavigation, 0.80); ok && plausibleBottomNavigationHint(hint.BBox, b.root) {
		navY = hint.BBox.Y
		navBox = hint.BBox
		navHint = &hint
	}
	slots := map[int][]ir.Node{}
	for _, node := range b.children() {
		if b.isUsed(node) || discardPhysicalNoise(node) || !bottomNavItem(node, b.root, navY) {
			continue
		}
		slot := clamp((centerX(node.SourceBBox)*5)/max(1, b.root.Width), 0, 4)
		slots[slot] = append(slots[slot], node)
	}
	if len(slots) < 4 {
		return ir.Node{}
	}
	nav := b.makeContainer("tree_bottom_nav_0001", ir.RoleBottomNavigation, navBox, proposalBottomNav)
	if navHint != nil {
		applyRegionHintEvidence(&nav, *navHint)
	}
	slotWidth := max(1, b.root.Width/5)
	var tabGroups []ir.Node
	for i := 0; i < 5; i++ {
		items := slots[i]
		if len(items) == 0 {
			continue
		}
		sortNodes(items)
		group := b.makeContainer(fmt.Sprintf("tree_bottom_tab_%04d", i+1), ir.RoleViewGroup, ir.BBox{
			X:      i * slotWidth,
			Y:      min(b.root.Height, navY+14),
			Width:  slotWidth,
			Height: min(102, max(1, b.root.Height-(navY+14))),
		}, proposalBottomTab)
		if i == 4 {
			group.SourceBBox.Width = b.root.Width - group.SourceBBox.X
			group.FigmaBBox.Width = group.SourceBBox.Width
		}
		group.Children = append(group.Children, items...)
		for _, item := range items {
			b.mark(item)
		}
		orderChildren(&group)
		tabGroups = append(tabGroups, group)
	}
	for _, node := range b.children() {
		if b.isUsed(node) || discardPhysicalNoise(node) || node.Role != ir.RoleBackground {
			continue
		}
		if node.SourceBBox.Y >= b.root.Height-35 && node.SourceBBox.Width >= b.root.Width/4 {
			tabGroups = append(tabGroups, node)
			b.mark(node)
		}
	}
	handle := b.takeOrMakeBackground("tree_home_indicator_0001", homeIndicatorBBox(b.root), "home_indicator_background")
	if wrapTabs {
		groupY := min(b.root.Height, navY+13)
		wrapper := b.makeContainer("tree_bottom_nav_group_0001", ir.RoleViewGroup, ir.BBox{
			X:      0,
			Y:      groupY,
			Width:  b.root.Width,
			Height: max(1, b.root.Height-groupY-1),
		}, proposalBottomNavWrapper)
		wrapper.Children = append(wrapper.Children, tabGroups...)
		wrapper.Children = append(wrapper.Children, b.takeOrMakeBackground("tree_bottom_nav_bg_0001", wrapper.SourceBBox, "bottom_navigation_region_background"))
		wrapper.Children = append(wrapper.Children, handle)
		orderChildren(&wrapper)
		nav.Children = append(nav.Children, wrapper)
	} else {
		nav.Children = append(nav.Children, tabGroups...)
		nav.Children = append(nav.Children, handle)
	}
	orderChildren(&nav)
	return nav
}

func (b *builder) buildSideRail(bottomNav ir.Node) ir.Node {
	navY := b.root.Height
	if bottomNav.ID != "" {
		navY = bottomNav.SourceBBox.Y
	}
	var topMarkers []ir.Node
	var content []ir.Node
	hasButton := false
	hasImage := false
	for _, node := range b.children() {
		if b.isUsed(node) || discardPhysicalNoise(node) {
			continue
		}
		box := node.SourceBBox
		if box.Y < max(200, b.root.Height/7) || box.Y >= navY {
			continue
		}
		if box.X >= b.root.Width-16 && box.Width <= 16 && box.Height >= 12 {
			topMarkers = append(topMarkers, node)
			continue
		}
		if box.X < int(float64(max(1, b.root.Width))*0.82) || box.Width > int(float64(max(1, b.root.Width))*0.24) {
			continue
		}
		switch node.Role {
		case ir.RoleButton, ir.RoleTextView, ir.RoleImageView, ir.RoleBackground:
			content = append(content, node)
			if node.Role == ir.RoleButton {
				hasButton = true
			}
			if node.Role == ir.RoleImageView {
				hasImage = true
			}
		}
	}
	if len(content) < 2 || !hasButton || !hasImage {
		return ir.Node{}
	}
	all := append(append([]ir.Node{}, topMarkers...), content...)
	sortNodes(topMarkers)
	sortNodes(content)
	outerWidth := clamp(int(float64(max(1, b.root.Width))*0.093), 48, 96)
	outerMargin := clamp(int(float64(max(1, b.root.Width))*0.032), 12, 32)
	outerY := max(0, minY(all)-clamp(int(float64(max(1, b.root.Height))*0.011), 12, 24))
	outerBottom := max(outerY+1, navY-clamp(int(float64(max(1, b.root.Height))*0.026), 28, 48))
	outer := b.makeContainer("tree_side_rail_0001", ir.RoleListView, ir.BBox{
		X:      max(0, b.root.Width-outerMargin-outerWidth),
		Y:      outerY,
		Width:  outerWidth,
		Height: outerBottom - outerY,
	}, proposalSideRail)
	for _, node := range topMarkers {
		outer.Children = append(outer.Children, sideRailMarkerBackground(node))
		b.mark(node)
	}
	innerY := outer.SourceBBox.Y + clamp(int(float64(max(1, b.root.Height))*0.085), 96, 140)
	innerHeight := max(1, navY-clamp(int(float64(max(1, b.root.Height))*0.031), 36, 52)-innerY)
	inner := b.makeContainer("tree_side_rail_inner_0001", ir.RoleListView, ir.BBox{
		X:      max(0, outer.SourceBBox.X-2),
		Y:      innerY,
		Width:  clamp(int(float64(max(1, b.root.Width))*0.143), 80, 112),
		Height: innerHeight,
	}, proposalSideRailInner)
	contentBox := unionNodes(content)
	stack := b.makeContainer("tree_side_rail_stack_0001", ir.RoleViewGroup, ir.BBox{
		X:      max(0, outer.SourceBBox.X-4),
		Y:      inner.SourceBBox.Y + clamp(int(float64(max(1, b.root.Height))*0.037), 48, 64),
		Width:  outer.SourceBBox.Width + 2,
		Height: inner.SourceBBox.Height,
	}, proposalSideRailStack)
	inner.FigmaBBox = ir.BBox{
		X:      contentBox.X,
		Y:      stack.FigmaBBox.Y,
		Width:  max(1, contentBox.Width),
		Height: inner.SourceBBox.Height,
	}
	inner.Children = append(inner.Children, stack)
	for _, node := range content {
		inner.Children = append(inner.Children, node)
		b.mark(node)
	}
	orderChildren(&inner)
	outer.Children = append(outer.Children, inner)
	orderChildren(&outer)
	return outer
}

func sideRailMarkerBackground(node ir.Node) ir.Node {
	node.Role = ir.RoleBackground
	node.FigmaType = ir.FigmaRoundedRectangle
	node.VisibleName = "Background"
	if len(node.Evidence) == 0 {
		node.Evidence = []ir.Evidence{{
			Kind:       "side_rail_marker_background",
			BBox:       node.SourceBBox,
			Confidence: 0.62,
			SourceID:   node.ID,
		}}
	} else {
		node.Evidence[0].Kind = "side_rail_marker_background"
		node.Evidence[0].BBox = node.SourceBBox
		if node.Evidence[0].Confidence == 0 {
			node.Evidence[0].Confidence = 0.62
		}
	}
	return node
}

func (b *builder) takeRootLateBackgrounds(bottomNav ir.Node) []ir.Node {
	if bottomNav.ID == "" {
		return nil
	}
	var out []ir.Node
	for _, node := range b.children() {
		if b.isUsed(node) || discardPhysicalNoise(node) || node.Role != ir.RoleBackground {
			continue
		}
		if node.SourceBBox.Width >= int(float64(max(1, b.root.Width))*0.82) &&
			node.SourceBBox.Height >= int(float64(max(1, bottomNav.SourceBBox.Height))*0.70) &&
			node.SourceBBox.Y <= bottomNav.SourceBBox.Y &&
			bottom(node.SourceBBox) >= bottom(bottomNav.SourceBBox)-8 {
			out = append(out, node)
			b.mark(node)
		}
	}
	sortNodes(out)
	return out
}

func (b *builder) buildBody(hasTopSearch bool, bottomNav ir.Node) ir.Node {
	bodyY := 0
	if hasTopSearch {
		bodyY = 160
	}
	bodyEnd := b.root.Height
	if bottomNav.ID != "" {
		bodyEnd = min(b.root.Height, max(0, bottomNav.SourceBBox.Y))
	}
	if bodyEnd <= bodyY {
		return ir.Node{}
	}
	body := b.makeContainer("tree_body_0001", ir.RoleListView, ir.BBox{X: 0, Y: bodyY, Width: b.root.Width, Height: bodyEnd - bodyY}, proposalBodyList)
	if !hasTopSearch {
		if action := b.buildActionBar(); action.ID != "" {
			body.Children = append(body.Children, action)
		}
	}

	for _, row := range b.buildRepeatedRows(body.SourceBBox) {
		body.Children = append(body.Children, row)
	}
	for _, region := range b.buildHintedRegions(body.SourceBBox) {
		body.Children = append(body.Children, region)
	}
	for _, section := range b.buildMajorSections(body.SourceBBox) {
		body.Children = append(body.Children, section)
	}
	for _, node := range b.remainingIn(body.SourceBBox) {
		body.Children = append(body.Children, node)
		b.mark(node)
	}
	if len(body.Children) == 0 {
		return ir.Node{}
	}
	orderChildren(&body)
	return body
}

func (b *builder) buildRepeatedRows(body ir.BBox) []ir.Node {
	candidates := b.rowCandidates(body)
	rows := bucketRows(candidates, b.root)
	var out []ir.Node
	for i, row := range rows {
		if i >= 6 {
			break
		}
		rowNodes := b.expandRow(row, body)
		if len(rowNodes) < 3 {
			continue
		}
		groups := b.rowGroups(rowNodes, len(out)+1)
		if !acceptRepeatedRowProposal(groups, b.root) {
			continue
		}
		listBox := padBBox(unionNodes(rowNodes), 8, 8, b.root)
		list := b.makeContainer(fmt.Sprintf("tree_row_list_%04d", len(out)+1), ir.RoleListView, listBox, proposalRepeatedRowList)
		for _, group := range groups {
			list.Children = append(list.Children, group)
		}
		for _, node := range rowNodes {
			b.mark(node)
		}
		orderChildren(&list)
		out = append(out, list)
	}
	sortNodes(out)
	return out
}

func acceptRepeatedRowProposal(groups []ir.Node, root ir.BBox) bool {
	if len(groups) == 0 {
		return false
	}
	rich := 0
	for _, group := range groups {
		if richRowGroup(group) {
			rich++
		}
	}
	switch len(groups) {
	case 1:
		return rich == 1 && len(groups[0].Children) >= 8
	case 2:
		return rich == 2 && rowGroupsHaveCompatibleSize(groups, 2.2)
	case 3:
		return rich >= 2 && rowGroupsHaveCompatibleSize(groups, 3.0)
	default:
		if rich >= 3 && rowGroupsHaveCompatibleSize(groups, 3.4) {
			return true
		}
		return rich >= 3 && rowCoverage(groups, root) >= 0.72
	}
}

func richRowGroup(group ir.Node) bool {
	if len(group.Children) < 2 {
		return false
	}
	for _, child := range group.Children {
		switch child.Role {
		case ir.RoleButton, ir.RoleEditText, ir.RoleImageView, ir.RoleBackground, ir.RoleBgButton, ir.RoleBgEditText:
			return true
		}
	}
	return false
}

func rowGroupsHaveCompatibleSize(groups []ir.Node, maxRatio float64) bool {
	minWidth := 0
	maxWidth := 0
	for _, group := range groups {
		width := max(1, group.SourceBBox.Width)
		if minWidth == 0 || width < minWidth {
			minWidth = width
		}
		if width > maxWidth {
			maxWidth = width
		}
	}
	return float64(maxWidth)/float64(max(1, minWidth)) <= maxRatio
}

func rowCoverage(groups []ir.Node, root ir.BBox) float64 {
	if len(groups) == 0 || root.Width <= 0 {
		return 0
	}
	return float64(unionNodes(groups).Width) / float64(root.Width)
}

func (b *builder) rowCandidates(body ir.BBox) []ir.Node {
	var out []ir.Node
	for _, node := range b.children() {
		if b.isUsed(node) || discardPhysicalNoise(node) || !centerInside(body, node.SourceBBox) || tinySpeck(node.SourceBBox) {
			continue
		}
		box := node.SourceBBox
		if box.Width >= int(float64(b.root.Width)*0.50) || box.Height > 190 {
			continue
		}
		switch node.Role {
		case ir.RoleBackground:
			if box.Width >= 45 && box.Height >= 18 {
				out = append(out, node)
			}
		case ir.RoleImageView:
			if box.Width >= 24 && box.Height >= 18 {
				out = append(out, node)
			}
		case ir.RoleButton:
			out = append(out, node)
		case ir.RoleTextView:
			if box.Width >= 18 && box.Height >= 12 {
				out = append(out, node)
			}
		}
	}
	return out
}

func bucketRows(nodes []ir.Node, root ir.BBox) [][]ir.Node {
	sortNodes(nodes)
	var rows [][]ir.Node
	for _, node := range nodes {
		placed := false
		cy := centerY(node.SourceBBox)
		for i := range rows {
			rowBox := unionNodes(rows[i])
			if abs(cy-centerY(rowBox)) <= 65 && unionBBox(rowBox, node.SourceBBox).Height <= 210 {
				rows[i] = append(rows[i], node)
				placed = true
				break
			}
		}
		if !placed {
			rows = append(rows, []ir.Node{node})
		}
	}
	out := rows[:0]
	for _, row := range rows {
		box := unionNodes(row)
		if len(row) >= 4 && box.Width >= int(float64(max(1, root.Width))*0.45) && box.Height <= 220 {
			out = append(out, row)
		}
	}
	return out
}

func (b *builder) expandRow(seeds []ir.Node, body ir.BBox) []ir.Node {
	rowBox := padBBox(unionNodes(seeds), 14, 24, b.root)
	rowBox = intersectWith(rowBox, body)
	var out []ir.Node
	for _, node := range b.children() {
		if b.isUsed(node) || discardPhysicalNoise(node) || tinySpeck(node.SourceBBox) {
			continue
		}
		if centerInside(rowBox, node.SourceBBox) || overlapRatio(node.SourceBBox, rowBox) >= 0.55 {
			if node.SourceBBox.Width >= int(float64(b.root.Width)*0.65) && node.SourceBBox.Height > rowBox.Height {
				continue
			}
			out = append(out, node)
		}
	}
	sortNodes(out)
	return out
}

func (b *builder) rowGroups(nodes []ir.Node, rowIndex int) []ir.Node {
	sort.SliceStable(nodes, func(i, j int) bool {
		return centerX(nodes[i].SourceBBox) < centerX(nodes[j].SourceBBox)
	})
	var groups [][]ir.Node
	for _, node := range nodes {
		placed := false
		cx := centerX(node.SourceBBox)
		for i := range groups {
			box := unionNodes(groups[i])
			if abs(cx-centerX(box)) <= max(48, box.Width/2+node.SourceBBox.Width/2+16) {
				groups[i] = append(groups[i], node)
				placed = true
				break
			}
		}
		if !placed {
			groups = append(groups, []ir.Node{node})
		}
	}
	var out []ir.Node
	for i, groupNodes := range groups {
		groupNodes = mergeAlignedBackgroundFragments(groupNodes)
		groupBox := padBBox(unionNodes(groupNodes), 6, 6, b.root)
		group := b.makeContainer(fmt.Sprintf("tree_row_%04d_item_%04d", rowIndex, i+1), ir.RoleViewGroup, groupBox, proposalRepeatedRowItem)
		sortNodes(groupNodes)
		group.Children = append(group.Children, groupNodes...)
		orderChildren(&group)
		out = append(out, group)
	}
	sortNodes(out)
	return out
}

func mergeAlignedBackgroundFragments(nodes []ir.Node) []ir.Node {
	used := make([]bool, len(nodes))
	var out []ir.Node
	for i := range nodes {
		if used[i] {
			continue
		}
		node := nodes[i]
		if !mergeableBackgroundFragment(node) {
			out = append(out, node)
			used[i] = true
			continue
		}
		indices := []int{i}
		mergedBox := node.SourceBBox
		used[i] = true
		changed := true
		for changed {
			changed = false
			for j := range nodes {
				if used[j] || !mergeableBackgroundFragment(nodes[j]) {
					continue
				}
				if alignedBackgroundFragment(mergedBox, nodes[j].SourceBBox) {
					indices = append(indices, j)
					mergedBox = unionBBox(mergedBox, nodes[j].SourceBBox)
					used[j] = true
					changed = true
				}
			}
		}
		if len(indices) == 1 {
			out = append(out, node)
			continue
		}
		out = append(out, mergedBackgroundFragment(nodes, indices, mergedBox))
	}
	return out
}

func mergeableBackgroundFragment(node ir.Node) bool {
	return node.Role == ir.RoleBackground && firstEvidenceKind(node) == "control_surface_background"
}

func alignedBackgroundFragment(a ir.BBox, b ir.BBox) bool {
	xTolerance := max(8, min(a.Width, b.Width)/12)
	if abs(a.X-b.X) > xTolerance || abs(bottomX(a)-bottomX(b)) > xTolerance {
		return false
	}
	if max(a.Width, b.Width) > 0 && float64(max(a.Width, b.Width))/float64(max(1, min(a.Width, b.Width))) > 1.18 {
		return false
	}
	verticalGap := max(a.Y, b.Y) - min(bottom(a), bottom(b))
	if verticalGap > 8 {
		return false
	}
	merged := unionBBox(a, b)
	return merged.Height <= 180
}

func mergedBackgroundFragment(nodes []ir.Node, indices []int, box ir.BBox) ir.Node {
	merged := nodes[indices[0]]
	merged.SourceBBox = box
	merged.FigmaBBox = box
	merged.Evidence = []ir.Evidence{{
		Kind:       firstEvidenceKind(merged),
		BBox:       box,
		Confidence: maxEvidenceConfidence(nodes, indices),
		SourceID:   joinedNodeIDs(nodes, indices),
		Notes:      "merged_card_background_fragments",
	}}
	return merged
}

func maxEvidenceConfidence(nodes []ir.Node, indices []int) float64 {
	out := 0.0
	for _, index := range indices {
		if len(nodes[index].Evidence) > 0 && nodes[index].Evidence[0].Confidence > out {
			out = nodes[index].Evidence[0].Confidence
		}
	}
	return out
}

func joinedNodeIDs(nodes []ir.Node, indices []int) string {
	out := make([]string, 0, len(indices))
	for _, index := range indices {
		out = append(out, nodes[index].ID)
	}
	sort.Strings(out)
	return strings.Join(out, ",")
}

func (b *builder) buildMajorSections(body ir.BBox) []ir.Node {
	var seeds []ir.Node
	for _, node := range b.children() {
		if b.isUsed(node) || discardPhysicalNoise(node) || !centerInside(body, node.SourceBBox) {
			continue
		}
		box := node.SourceBBox
		if (node.Role == ir.RoleImageView || node.Role == ir.RoleBackground) &&
			box.Width >= int(float64(b.root.Width)*0.45) && box.Height >= 100 {
			seeds = append(seeds, node)
		}
	}
	sort.SliceStable(seeds, func(i, j int) bool {
		return area(seeds[i].SourceBBox) > area(seeds[j].SourceBBox)
	})
	var out []ir.Node
	for _, seed := range seeds {
		if b.isUsed(seed) {
			continue
		}
		sectionBox := padBBox(seed.SourceBBox, 8, 8, b.root)
		sectionBox = intersectWith(sectionBox, body)
		var nodes []ir.Node
		for _, node := range b.children() {
			if b.isUsed(node) || discardPhysicalNoise(node) || tinySpeck(node.SourceBBox) {
				continue
			}
			if centerInside(sectionBox, node.SourceBBox) || overlapRatio(node.SourceBBox, sectionBox) >= 0.40 {
				nodes = append(nodes, node)
			}
		}
		if len(nodes) < 2 {
			continue
		}
		group := b.makeContainer(fmt.Sprintf("tree_section_%04d", len(out)+1), ir.RoleViewGroup, unionNodes(nodes), proposalMajorSection)
		group.SourceBBox = padBBox(group.SourceBBox, 6, 6, b.root)
		group.FigmaBBox = group.SourceBBox
		sortNodes(nodes)
		group.Children = append(group.Children, nodes...)
		for _, node := range nodes {
			b.mark(node)
		}
		orderChildren(&group)
		out = append(out, group)
		if len(out) >= 4 {
			break
		}
	}
	sortNodes(out)
	return out
}

func (b *builder) buildHintedRegions(body ir.BBox) []ir.Node {
	roles := map[ir.Role]bool{
		ir.RoleListView:  true,
		ir.RoleViewGroup: true,
	}
	hints := b.orderedRegionHints(roles, 0.88)
	var out []ir.Node
	for _, hint := range hints {
		if !acceptBodyRegionHint(hint, body, b.root) {
			continue
		}
		box := intersectWith(hint.BBox, body)
		nodes := b.regionHintChildren(box, body)
		slots := b.hintedRegionSlots(nodes, len(out)+1)
		if !acceptHintedRegionSlots(slots) {
			continue
		}
		list := b.makeContainer(fmt.Sprintf("tree_hint_list_%04d", len(out)+1), ir.RoleListView, box, proposalHintedSlotList)
		list.Evidence[0].Confidence = hint.Confidence
		list.Evidence[0].SourceID = hint.SourceID
		list.Evidence[0].Notes = "assembly_region_hint"
		if hint.Label != "" {
			list.Evidence[0].Notes += "/label=" + hint.Label
		}
		for _, slot := range slots {
			list.Children = append(list.Children, slot)
			for _, child := range slot.Children {
				b.mark(child)
			}
		}
		orderChildren(&list)
		out = append(out, list)
		if len(out) >= 6 {
			break
		}
	}
	sortNodes(out)
	return out
}

func (b *builder) hintedRegionSlots(nodes []ir.Node, regionIndex int) []ir.Node {
	if len(nodes) < 2 {
		return nil
	}
	sort.SliceStable(nodes, func(i, j int) bool {
		if centerX(nodes[i].SourceBBox) != centerX(nodes[j].SourceBBox) {
			return centerX(nodes[i].SourceBBox) < centerX(nodes[j].SourceBBox)
		}
		if nodes[i].SourceBBox.Y != nodes[j].SourceBBox.Y {
			return nodes[i].SourceBBox.Y < nodes[j].SourceBBox.Y
		}
		return nodes[i].ID < nodes[j].ID
	})
	groups := splitHintedSlotGroups(nodes)
	var out []ir.Node
	for _, groupNodes := range groups {
		groupNodes = mergeAlignedBackgroundFragments(groupNodes)
		if !acceptHintedSlotChildren(groupNodes) {
			continue
		}
		groupBox := padBBox(unionNodes(groupNodes), 4, 4, b.root)
		group := b.makeContainer(fmt.Sprintf("tree_hint_%04d_slot_%04d", regionIndex, len(out)+1), ir.RoleViewGroup, groupBox, proposalHintedSlot)
		sortNodes(groupNodes)
		group.Children = append(group.Children, groupNodes...)
		orderChildren(&group)
		out = append(out, group)
	}
	sortNodes(out)
	return out
}

func splitHintedSlotGroups(nodes []ir.Node) [][]ir.Node {
	var groups [][]ir.Node
	for _, node := range nodes {
		placed := false
		cx := centerX(node.SourceBBox)
		for i := range groups {
			box := unionNodes(groups[i])
			tolerance := max(44, max(box.Width, node.SourceBBox.Width)/2+28)
			if abs(cx-centerX(box)) <= tolerance {
				groups[i] = append(groups[i], node)
				placed = true
				break
			}
		}
		if !placed {
			groups = append(groups, []ir.Node{node})
		}
	}
	return groups
}

func (b *builder) regionHintChildren(box ir.BBox, body ir.BBox) []ir.Node {
	var out []ir.Node
	for _, node := range b.children() {
		if b.isUsed(node) || discardPhysicalNoise(node) || tinySpeck(node.SourceBBox) || !regionHintChildRole(node.Role) {
			continue
		}
		if !centerInside(body, node.SourceBBox) && overlapRatio(node.SourceBBox, body) < 0.50 {
			continue
		}
		if !centerInside(box, node.SourceBBox) && overlapRatio(node.SourceBBox, box) < 0.45 {
			continue
		}
		if regionHintChildTooLarge(node, box, b.root) {
			continue
		}
		out = append(out, node)
	}
	sortNodes(out)
	return out
}

func regionHintChildRole(role ir.Role) bool {
	switch role {
	case ir.RoleTextView, ir.RoleImageView, ir.RoleButton, ir.RoleEditText, ir.RoleBackground, ir.RoleBgButton, ir.RoleBgEditText:
		return true
	default:
		return false
	}
}

func regionHintChildTooLarge(node ir.Node, box ir.BBox, root ir.BBox) bool {
	if area(node.SourceBBox) > area(box)*11/10 {
		return true
	}
	if (node.Role == ir.RoleImageView || node.Role == ir.RoleBackground) && area(node.SourceBBox) > area(box)*45/100 {
		return true
	}
	if node.Role == ir.RoleBackground &&
		node.SourceBBox.Width >= int(float64(max(1, root.Width))*0.90) &&
		node.SourceBBox.Height >= int(float64(max(1, root.Height))*0.45) {
		return true
	}
	return false
}

func acceptBodyRegionHint(hint regionHint, body ir.BBox, root ir.BBox) bool {
	if hint.BBox.Width <= 0 || hint.BBox.Height <= 0 || !intersects(hint.BBox, body) {
		return false
	}
	rootArea := max(1, area(root))
	hintArea := area(hint.BBox)
	if hintArea < rootArea/250 {
		return false
	}
	if hintArea > rootArea*35/100 {
		return false
	}
	if hint.BBox.Height > max(1, body.Height)*75/100 {
		return false
	}
	return true
}

func acceptHintedRegionSlots(slots []ir.Node) bool {
	if len(slots) < 3 {
		return false
	}
	rich := 0
	for _, slot := range slots {
		if richHintedSlot(slot) {
			rich++
		}
	}
	if rich < max(2, len(slots)-1) {
		return false
	}
	return rowGroupsHaveCompatibleSize(slots, 3.4)
}

func richHintedSlot(slot ir.Node) bool {
	return len(slot.Children) >= 2 && slotHasForeground(slot) && slotHasRichVisual(slot)
}

func slotHasForeground(slot ir.Node) bool {
	for _, child := range slot.Children {
		switch child.Role {
		case ir.RoleTextView, ir.RoleImageView, ir.RoleButton, ir.RoleEditText:
			return true
		}
	}
	return false
}

func slotHasRichVisual(slot ir.Node) bool {
	for _, child := range slot.Children {
		switch child.Role {
		case ir.RoleImageView, ir.RoleButton, ir.RoleEditText, ir.RoleBackground, ir.RoleBgButton, ir.RoleBgEditText:
			return true
		}
	}
	return false
}

func acceptHintedSlotChildren(nodes []ir.Node) bool {
	if len(nodes) < 2 {
		return false
	}
	rich := 0
	foreground := 0
	for _, node := range nodes {
		switch node.Role {
		case ir.RoleImageView, ir.RoleButton, ir.RoleEditText, ir.RoleBgButton, ir.RoleBgEditText:
			rich++
			foreground++
		case ir.RoleTextView:
			foreground++
		case ir.RoleBackground:
			rich++
		}
	}
	if rich == 0 || foreground < 2 {
		return false
	}
	return true
}

func (b *builder) remainingIn(box ir.BBox) []ir.Node {
	var out []ir.Node
	for _, node := range b.children() {
		if b.isUsed(node) || discardPhysicalNoise(node) || !centerInside(box, node.SourceBBox) {
			continue
		}
		out = append(out, node)
	}
	sortNodes(out)
	return out
}

func (b *builder) remainingRootChildren() []ir.Node {
	var out []ir.Node
	for _, node := range b.children() {
		if b.isUsed(node) || discardPhysicalNoise(node) {
			continue
		}
		out = append(out, node)
		b.mark(node)
	}
	sortNodes(out)
	return out
}

func (b *builder) makeContainer(id string, role ir.Role, box ir.BBox, kind proposalKind) ir.Node {
	return ir.Node{
		ID:          id,
		Role:        role,
		SourceBBox:  box,
		FigmaBBox:   box,
		FigmaType:   ir.FigmaFrame,
		VisibleName: containerVisibleName(role),
		SourcePath:  id,
		Evidence: []ir.Evidence{{
			Kind:       string(kind),
			BBox:       box,
			Confidence: 0.62,
			SourceID:   id,
		}},
		Style: ir.Style{Visible: true, Opacity: 1},
	}
}

func applyRegionHintEvidence(node *ir.Node, hint regionHint) {
	if len(node.Evidence) == 0 {
		return
	}
	node.Evidence[0].BBox = hint.BBox
	node.Evidence[0].Confidence = hint.Confidence
	node.Evidence[0].SourceID = hint.SourceID
	node.Evidence[0].Notes = "assembly_region_hint"
	if hint.Label != "" {
		node.Evidence[0].Notes += "/label=" + hint.Label
	}
}

func (b *builder) takeOrMakeBackground(id string, box ir.BBox, kind string) ir.Node {
	for _, node := range b.children() {
		if b.isUsed(node) || node.Role != ir.RoleBackground {
			continue
		}
		if iou(node.SourceBBox, box) >= 0.58 {
			b.mark(node)
			return node
		}
	}
	return ir.Node{
		ID:          id,
		Role:        ir.RoleBackground,
		SourceBBox:  box,
		FigmaBBox:   box,
		FigmaType:   ir.FigmaRoundedRectangle,
		VisibleName: "Background",
		SourcePath:  id,
		Evidence: []ir.Evidence{{
			Kind:       kind,
			BBox:       box,
			Confidence: 0.58,
			SourceID:   id,
		}},
		Style: ir.Style{Visible: true, Opacity: 1},
	}
}

func containerVisibleName(role ir.Role) string {
	switch role {
	case ir.RoleButton:
		return "Button"
	case ir.RoleEditText:
		return "Text"
	case ir.RoleRoot:
		return "Root"
	default:
		return "Groups"
	}
}

func (b *builder) mark(node ir.Node) {
	b.used[node.ID] = true
}

func (b *builder) isUsed(node ir.Node) bool {
	return b.used[node.ID]
}

func topStatusHeight(root ir.BBox) int {
	return clamp(int(float64(max(1, root.Height))*0.047), 56, 74)
}

func plausibleTopRegionHint(box ir.BBox, root ir.BBox) bool {
	if box.Width < max(1, root.Width)/2 || box.Y > max(120, root.Height/10) {
		return false
	}
	return box.Height >= 24 && box.Height <= max(96, root.Height/5)
}

func plausibleBottomNavigationHint(box ir.BBox, root ir.BBox) bool {
	if box.Width < int(float64(max(1, root.Width))*0.70) {
		return false
	}
	if box.Y < int(float64(max(1, root.Height))*0.70) {
		return false
	}
	return box.Height >= 64 && box.Height <= max(180, root.Height/5)
}

func topChromeNode(node ir.Node, box ir.BBox) bool {
	if !intersects(node.SourceBBox, box) && centerY(node.SourceBBox) > bottom(box)+8 {
		return false
	}
	switch node.Role {
	case ir.RoleTextView, ir.RoleImageView, ir.RoleButton:
		return true
	case ir.RoleBackground:
		return area(node.SourceBBox) > 0 && node.SourceBBox.Height <= 18
	default:
		return false
	}
}

func smallChromeLeaf(node ir.Node) bool {
	switch node.Role {
	case ir.RoleTextView, ir.RoleImageView:
		return true
	case ir.RoleBackground:
		return node.SourceBBox.Width < 80 && node.SourceBBox.Height < 40
	default:
		return false
	}
}

func bottomNavItem(node ir.Node, root ir.BBox, navY int) bool {
	box := node.SourceBBox
	if centerY(box) < navY+20 || box.Y < navY-6 {
		return false
	}
	if box.Width > root.Width/3 || box.Height > 80 || tinySpeck(box) {
		return false
	}
	return node.Role == ir.RoleTextView || node.Role == ir.RoleImageView
}

func homeIndicatorBBox(root ir.BBox) ir.BBox {
	width := clamp(int(float64(max(1, root.Width))*0.354), 96, root.Width)
	bottomInset := clamp(int(float64(max(1, root.Height))*0.010), 8, 18)
	return ir.BBox{
		X:      max(0, (root.Width-width)/2),
		Y:      max(0, root.Height-bottomInset-8),
		Width:  width,
		Height: 8,
	}
}

func edgeRailItem(box ir.BBox, root ir.BBox) bool {
	return box.X <= 24 || bottomX(box) >= root.Width-24
}

func discardPhysicalNoise(node ir.Node) bool {
	if node.Role == ir.RoleButton || node.Role == ir.RoleEditText || node.Role == ir.RoleBgButton || node.Role == ir.RoleBgEditText || node.Role == ir.RoleTextView {
		return false
	}
	box := node.SourceBBox
	if box.Width <= 0 || box.Height <= 0 {
		return true
	}
	if box.Width <= 8 && box.Height <= 8 {
		return true
	}
	if node.Role == ir.RoleBackground {
		if firstEvidenceNotes(node) == "layer_background_token" && area(box) < 900 && box.Width < 120 && box.Height < 24 {
			return true
		}
		return false
	}
	if node.Role == ir.RoleImageView && area(box) < 80 {
		return true
	}
	return false
}

func firstEvidenceNotes(node ir.Node) string {
	if len(node.Evidence) == 0 {
		return ""
	}
	return node.Evidence[0].Notes
}

func tinySpeck(box ir.BBox) bool {
	return box.Width <= 8 && box.Height <= 8
}

func orderChildren(node *ir.Node) {
	for i := range node.Children {
		orderChildren(&node.Children[i])
	}
	sort.SliceStable(node.Children, func(i, j int) bool {
		ai, aj := orderBucket(node.Children[i].Role), orderBucket(node.Children[j].Role)
		if ai != aj {
			return ai < aj
		}
		a, b := node.Children[i].SourceBBox, node.Children[j].SourceBBox
		if a.Y != b.Y {
			return a.Y < b.Y
		}
		if a.X != b.X {
			return a.X < b.X
		}
		return node.Children[i].ID < node.Children[j].ID
	})
}

func orderBucket(role ir.Role) int {
	switch role {
	case ir.RoleBackground, ir.RoleBgButton, ir.RoleBgEditText:
		return 3
	case ir.RoleImageView:
		return 1
	default:
		return 0
	}
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

func unionNodes(nodes []ir.Node) ir.BBox {
	if len(nodes) == 0 {
		return ir.BBox{}
	}
	out := nodes[0].SourceBBox
	for _, node := range nodes[1:] {
		out = unionBBox(out, node.SourceBBox)
	}
	return out
}

func minY(nodes []ir.Node) int {
	if len(nodes) == 0 {
		return 0
	}
	out := nodes[0].SourceBBox.Y
	for _, node := range nodes[1:] {
		out = min(out, node.SourceBBox.Y)
	}
	return out
}

func padBBox(box ir.BBox, xPad int, yPad int, root ir.BBox) ir.BBox {
	x1 := max(0, box.X-xPad)
	y1 := max(0, box.Y-yPad)
	x2 := min(root.Width, box.X+box.Width+xPad)
	y2 := min(root.Height, box.Y+box.Height+yPad)
	return ir.BBox{X: x1, Y: y1, Width: max(1, x2-x1), Height: max(1, y2-y1)}
}

func intersectWith(a ir.BBox, b ir.BBox) ir.BBox {
	x1 := max(a.X, b.X)
	y1 := max(a.Y, b.Y)
	x2 := min(bottomX(a), bottomX(b))
	y2 := min(bottom(a), bottom(b))
	if x2 <= x1 || y2 <= y1 {
		return a
	}
	return ir.BBox{X: x1, Y: y1, Width: x2 - x1, Height: y2 - y1}
}

func centerInside(parent, child ir.BBox) bool {
	cx := centerX(child)
	cy := centerY(child)
	return parent.X <= cx && cx <= bottomX(parent) && parent.Y <= cy && cy <= bottom(parent)
}

func intersects(a, b ir.BBox) bool {
	return max(a.X, b.X) < min(bottomX(a), bottomX(b)) && max(a.Y, b.Y) < min(bottom(a), bottom(b))
}

func overlapRatio(a, b ir.BBox) float64 {
	x1 := max(a.X, b.X)
	y1 := max(a.Y, b.Y)
	x2 := min(bottomX(a), bottomX(b))
	y2 := min(bottom(a), bottom(b))
	if x2 <= x1 || y2 <= y1 {
		return 0
	}
	return float64((x2-x1)*(y2-y1)) / float64(max(1, area(a)))
}

func iou(a ir.BBox, b ir.BBox) float64 {
	x1 := max(a.X, b.X)
	y1 := max(a.Y, b.Y)
	x2 := min(bottomX(a), bottomX(b))
	y2 := min(bottom(a), bottom(b))
	if x2 <= x1 || y2 <= y1 {
		return 0
	}
	intersection := (x2 - x1) * (y2 - y1)
	return float64(intersection) / float64(max(1, area(a)+area(b)-intersection))
}

func unionBBox(a, b ir.BBox) ir.BBox {
	x1 := min(a.X, b.X)
	y1 := min(a.Y, b.Y)
	x2 := max(bottomX(a), bottomX(b))
	y2 := max(bottom(a), bottom(b))
	return ir.BBox{X: x1, Y: y1, Width: x2 - x1, Height: y2 - y1}
}

func centerX(box ir.BBox) int {
	return box.X + box.Width/2
}

func centerY(box ir.BBox) int {
	return box.Y + box.Height/2
}

func bottomX(box ir.BBox) int {
	return box.X + box.Width
}

func bottom(box ir.BBox) int {
	return box.Y + box.Height
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

func clamp(value int, low int, high int) int {
	return min(max(value, low), high)
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
