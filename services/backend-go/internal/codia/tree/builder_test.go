package tree

import (
	"strings"
	"testing"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/ir"
)

func TestBuildCreatesRoleRegionsAndKeepsBackgroundLate(t *testing.T) {
	doc := fixtureDoc([]ir.Node{
		text("time", 70, 26, 70, 30, "11:02"),
		control("search", ir.RoleEditText, 26, 160, 455, 58),
		control("right-a", ir.RoleButton, 500, 160, 60, 58),
		control("right-b", ir.RoleButton, 580, 160, 58, 58),
		image("hero", 24, 238, 618, 915),
		text("title", 50, 257, 135, 60, "Title"),
		image("tab1i", 45, 1314, 41, 40),
		text("tab1t", 46, 1356, 39, 24, "A"),
		image("tab2i", 178, 1311, 42, 41),
		text("tab2t", 180, 1358, 37, 22, "B"),
		image("tab3i", 303, 1310, 59, 45),
		text("tab3t", 307, 1358, 48, 20, "C"),
		image("tab4i", 446, 1314, 38, 37),
		text("tab4t", 443, 1354, 42, 28, "D"),
		image("tab5i", 576, 1312, 44, 41),
		text("tab5t", 579, 1358, 37, 22, "E"),
		background("nav-bg", 0, 1298, 665, 141),
	})
	out, err := Build(doc)
	if err != nil {
		t.Fatalf("Build() error = %v", err)
	}
	if out.Summary.RoleCounts[string(ir.RoleBottomNavigation)] != 1 {
		t.Fatalf("expected bottom navigation, got %#v", out.Summary.RoleCounts)
	}
	if out.Summary.RoleCounts[string(ir.RoleViewGroup)] == 0 || out.Summary.RoleCounts[string(ir.RoleListView)] == 0 {
		t.Fatalf("expected structural regions, got %#v", out.Summary.RoleCounts)
	}
	if out.Summary.MaxDepth < 2 {
		t.Fatalf("expected nested tree, maxDepth=%d", out.Summary.MaxDepth)
	}
	nav := firstRole(out.Root, ir.RoleBottomNavigation)
	if nav == nil {
		t.Fatalf("expected bottom navigation node")
	}
	if !containsRole(*nav, ir.RoleBackground) {
		t.Fatalf("expected bottom navigation subtree to own its background")
	}
	if !backgroundsAreLate(out.Root) {
		t.Fatalf("expected backgrounds to stay after foreground siblings")
	}
	if rootFlatLeafCount(out.Root.Children) >= len(doc.Root.Children)-1 {
		t.Fatalf("tree builder left almost everything root-flat: %#v", out.Root.Children)
	}
	if nav.Evidence[0].Kind != string(proposalBottomNav) {
		t.Fatalf("expected bottom navigation proposal evidence, got %#v", nav.Evidence)
	}
	report := MarkdownReport(out)
	if !strings.Contains(report, "bottom_navigation_candidate") || !strings.Contains(report, "body_list_owner") {
		t.Fatalf("expected proposal evidence in tree report:\n%s", report)
	}
}

func TestBuildSkipsWeakTextOnlyRowsButKeepsRichRepeatedRows(t *testing.T) {
	rich := []ir.Node{
		text("r1t", 50, 260, 80, 20, "A"),
		image("r1i", 60, 295, 80, 80),
		background("r1bg", 45, 250, 130, 150),
		text("r2t", 220, 260, 80, 20, "B"),
		image("r2i", 230, 295, 80, 80),
		background("r2bg", 215, 250, 130, 150),
		text("r3t", 390, 260, 80, 20, "C"),
		image("r3i", 400, 295, 80, 80),
		background("r3bg", 385, 250, 130, 150),
	}
	weak := []ir.Node{
		text("w1", 45, 900, 90, 24, "One"),
		text("w2", 160, 900, 90, 24, "Two"),
		text("w3", 285, 900, 90, 24, "Three"),
		text("w4", 410, 900, 90, 24, "Four"),
		text("w5", 530, 900, 80, 24, "Five"),
	}
	out, err := Build(fixtureDoc(append(rich, weak...)))
	if err != nil {
		t.Fatalf("Build() error = %v", err)
	}
	if countEvidence(out.Root, string(proposalRepeatedRowList)) != 1 {
		t.Fatalf("expected only rich repeated row list to materialize:\n%s", MarkdownReport(out))
	}
	for _, node := range flattenNodes(out.Root) {
		if len(node.Evidence) > 0 && node.Evidence[0].Kind == string(proposalRepeatedRowList) && node.SourceBBox.Y > 800 {
			t.Fatalf("weak text-only row materialized: %#v", node)
		}
	}
}

func TestMergeAlignedBackgroundFragments(t *testing.T) {
	nodes := []ir.Node{
		backgroundWithEvidence("top", "control_surface_background", 20, 40, 120, 54),
		text("label", 48, 55, 64, 24, "Label"),
		backgroundWithEvidence("bottom", "control_surface_background", 21, 88, 119, 58),
		backgroundWithEvidence("solid", "solid_background", 170, 40, 120, 110),
		backgroundWithEvidence("offset", "control_surface_background", 310, 40, 95, 54),
		backgroundWithEvidence("offset-bottom", "control_surface_background", 333, 88, 95, 58),
	}
	out := mergeAlignedBackgroundFragments(nodes)
	backgrounds := []ir.Node{}
	for _, node := range out {
		if node.Role == ir.RoleBackground {
			backgrounds = append(backgrounds, node)
		}
	}
	if len(backgrounds) != 4 {
		t.Fatalf("expected only aligned control-surface pair to merge, got %#v", backgrounds)
	}
	merged := findNode(out, "top")
	if merged == nil {
		t.Fatalf("expected merged node to keep first fragment id: %#v", out)
	}
	if merged.SourceBBox != (ir.BBox{X: 20, Y: 40, Width: 120, Height: 106}) {
		t.Fatalf("unexpected merged bbox: %#v", merged.SourceBBox)
	}
	if len(merged.Evidence) == 0 || merged.Evidence[0].SourceID != "bottom,top" || merged.Evidence[0].Notes != "merged_card_background_fragments" {
		t.Fatalf("unexpected merged evidence: %#v", merged.Evidence)
	}
}

func TestBuildCreatesSideRailWhenRightEdgeEvidenceExists(t *testing.T) {
	children := []ir.Node{
		control("search", ir.RoleEditText, 27, 160, 454, 58),
		image("tab1i", 45, 1314, 41, 40),
		text("tab1t", 46, 1356, 39, 24, "A"),
		image("tab2i", 178, 1311, 42, 41),
		text("tab2t", 180, 1358, 37, 22, "B"),
		image("tab3i", 303, 1310, 59, 45),
		text("tab3t", 307, 1358, 48, 20, "C"),
		image("tab4i", 446, 1314, 38, 37),
		text("tab4t", 443, 1354, 42, 28, "D"),
		image("tab5i", 576, 1312, 44, 41),
		text("tab5t", 579, 1358, 37, 22, "E"),
		image("rail-marker", 654, 237, 6, 36),
		image("rail-card", 558, 1180, 95, 78),
		text("rail-label", 569, 1204, 31, 22, "Card"),
		control("rail-button", ir.RoleButton, 558, 1229, 95, 29),
	}
	out, err := Build(fixtureDoc(children))
	if err != nil {
		t.Fatalf("Build() error = %v", err)
	}
	if countEvidence(out.Root, string(proposalSideRail)) != 1 ||
		countEvidence(out.Root, string(proposalSideRailInner)) != 1 ||
		countEvidence(out.Root, string(proposalSideRailStack)) != 1 {
		t.Fatalf("expected side rail containers:\n%s", MarkdownReport(out))
	}
	rail := firstEvidence(out.Root, string(proposalSideRail))
	if rail == nil || rail.Role != ir.RoleListView {
		t.Fatalf("expected ListView side rail, got %#v", rail)
	}
	if !containsID(*rail, "rail-button") || !containsID(*rail, "rail-card") {
		t.Fatalf("expected rail content to be owned by side rail: %#v", rail)
	}
	marker := findNode(flattenNodes(*rail), "rail-marker")
	if marker == nil || marker.Role != ir.RoleBackground || marker.VisibleName != "Background" {
		t.Fatalf("expected side rail marker to emit as Background, got %#v", marker)
	}
	if len(marker.Evidence) == 0 || marker.Evidence[0].Kind != "side_rail_marker_background" {
		t.Fatalf("expected marker background evidence, got %#v", marker.Evidence)
	}
}

func TestBuildUsesBottomNavigationRegionHintForContainerBBox(t *testing.T) {
	doc := fixtureDoc([]ir.Node{
		image("tab1i", 45, 1314, 41, 40),
		text("tab1t", 46, 1356, 39, 24, "A"),
		image("tab2i", 178, 1311, 42, 41),
		text("tab2t", 180, 1358, 37, 22, "B"),
		image("tab3i", 303, 1310, 59, 45),
		text("tab3t", 307, 1358, 48, 20, "C"),
		image("tab4i", 446, 1314, 38, 37),
		text("tab4t", 443, 1354, 42, 28, "D"),
		image("tab5i", 576, 1312, 44, 41),
		text("tab5t", 579, 1358, 37, 22, "E"),
	})
	hintBox := ir.BBox{X: 0, Y: 1297, Width: 665, Height: 118}
	doc.Root.Evidence = []ir.Evidence{regionHintEvidence("det_nav", ir.RoleBottomNavigation, hintBox, 0.98)}

	out, err := Build(doc)
	if err != nil {
		t.Fatalf("Build() error = %v", err)
	}
	nav := firstRole(out.Root, ir.RoleBottomNavigation)
	if nav == nil {
		t.Fatalf("expected bottom navigation node")
	}
	if nav.SourceBBox != hintBox {
		t.Fatalf("expected bottom nav bbox from assembly hint, got %#v", nav.SourceBBox)
	}
	if !containsID(*nav, "tab3i") || !containsID(*nav, "tab5t") {
		t.Fatalf("bottom nav hint must still own real tab children: %#v", nav)
	}
}

func TestBuildClipsBodyToBottomNavigationHint(t *testing.T) {
	doc := fixtureDoc([]ir.Node{
		text("content", 52, 1180, 120, 28, "Content"),
		image("tab1i", 45, 1314, 41, 40),
		text("tab1t", 46, 1356, 39, 24, "A"),
		image("tab2i", 178, 1311, 42, 41),
		text("tab2t", 180, 1358, 37, 22, "B"),
		image("tab3i", 303, 1310, 59, 45),
		text("tab3t", 307, 1358, 48, 20, "C"),
		image("tab4i", 446, 1314, 38, 37),
		text("tab4t", 443, 1354, 42, 28, "D"),
		image("tab5i", 576, 1312, 44, 41),
		text("tab5t", 579, 1358, 37, 22, "E"),
	})
	hintBox := ir.BBox{X: 0, Y: 1297, Width: 665, Height: 118}
	doc.Root.Evidence = []ir.Evidence{regionHintEvidence("det_nav", ir.RoleBottomNavigation, hintBox, 0.98)}

	out, err := Build(doc)
	if err != nil {
		t.Fatalf("Build() error = %v", err)
	}
	body := firstEvidence(out.Root, string(proposalBodyList))
	nav := firstRole(out.Root, ir.RoleBottomNavigation)
	if body == nil || nav == nil {
		t.Fatalf("expected both body and bottom nav:\n%s", MarkdownReport(out))
	}
	if bottom(body.SourceBBox) > nav.SourceBBox.Y {
		t.Fatalf("body overlaps bottom nav: body=%#v nav=%#v", body.SourceBBox, nav.SourceBBox)
	}
	if containsID(*body, "tab3i") || containsID(*body, "tab5t") {
		t.Fatalf("body must not consume bottom nav children: %#v", body)
	}
	if !containsID(*nav, "tab3i") || !containsID(*nav, "tab5t") {
		t.Fatalf("bottom nav should still own tab children: %#v", nav)
	}
}

func TestBuildRejectsLowerActionBarHintAndKeepsLargeImageOutOfTopChrome(t *testing.T) {
	doc := fixtureDoc([]ir.Node{
		control("browser-pill", ir.RoleButton, 250, 15, 166, 40),
		text("time", 68, 27, 79, 31, "11:02"),
		image("wifi", 573, 33, 45, 22),
		text("section-title", 268, 90, 124, 41, "会员专区"),
		image("large-card", 27, 150, 611, 681),
	})
	doc.Root.Evidence = []ir.Evidence{regionHintEvidence("det_action_wrong", ir.RoleActionBar, ir.BBox{X: 0, Y: 84, Width: 665, Height: 76}, 0.98)}

	out, err := Build(doc)
	if err != nil {
		t.Fatalf("Build() error = %v", err)
	}
	action := firstEvidence(out.Root, string(proposalActionBar))
	if action == nil {
		t.Fatalf("expected action bar from real top chrome:\n%s", MarkdownReport(out))
	}
	if action.SourceBBox.Y != 0 || action.SourceBBox.Height != 74 {
		t.Fatalf("lower detector hint must not become the top chrome bbox: %#v", action.SourceBBox)
	}
	if containsID(*action, "large-card") {
		t.Fatalf("top chrome consumed a large body image: %#v", action.Children)
	}
	body := firstEvidence(out.Root, string(proposalBodyList))
	if body == nil || !containsID(*body, "large-card") {
		t.Fatalf("large body image should remain in body ownership:\n%s", MarkdownReport(out))
	}
}

func TestBuildAddsBodyVisualBackingImage(t *testing.T) {
	doc := fixtureDoc([]ir.Node{
		text("content", 52, 320, 120, 28, "Content"),
	})

	out, err := Build(doc)
	if err != nil {
		t.Fatalf("Build() error = %v", err)
	}
	body := firstEvidence(out.Root, string(proposalBodyList))
	if body == nil {
		t.Fatalf("expected body:\n%s", MarkdownReport(out))
	}
	backing := firstEvidence(*body, string(proposalVisualBacking))
	if backing == nil {
		t.Fatalf("expected visual backing image in body: %#v", body.Children)
	}
	if backing.Role != ir.RoleImageView || backing.SourceBBox != body.SourceBBox {
		t.Fatalf("unexpected backing image: role=%s bbox=%#v body=%#v", backing.Role, backing.SourceBBox, body.SourceBBox)
	}
	if backing.Asset == nil || backing.Asset.Kind != "crop" {
		t.Fatalf("backing image must crop from source PNG: %#v", backing.Asset)
	}
}

func TestBuildCreatesHintedSlotListOnlyWithRealChildren(t *testing.T) {
	doc := fixtureDoc([]ir.Node{
		image("slot1i", 60, 300, 80, 60),
		text("slot1t", 58, 570, 86, 22, "One"),
		image("slot2i", 230, 302, 80, 58),
		text("slot2t", 228, 572, 84, 22, "Two"),
		image("slot3i", 400, 301, 82, 59),
		text("slot3t", 398, 571, 86, 22, "Three"),
		text("outside", 50, 900, 90, 24, "Outside"),
	})
	hintBox := ir.BBox{X: 40, Y: 270, Width: 500, Height: 350}
	doc.Root.Evidence = []ir.Evidence{regionHintEvidence("det_list", ir.RoleListView, hintBox, 0.95)}

	out, err := Build(doc)
	if err != nil {
		t.Fatalf("Build() error = %v", err)
	}
	region := firstEvidence(out.Root, string(proposalHintedSlotList))
	if region == nil {
		t.Fatalf("expected hinted slot list:\n%s", MarkdownReport(out))
	}
	if region.Role != ir.RoleListView {
		t.Fatalf("expected hinted ListView, got %#v", region.Role)
	}
	if region.SourceBBox != hintBox {
		t.Fatalf("expected hinted bbox authority, got %#v", region.SourceBBox)
	}
	if countEvidence(*region, string(proposalHintedSlot)) != 3 {
		t.Fatalf("expected three hinted slots: %#v", region.Children)
	}
	if !containsID(*region, "slot1i") || !containsID(*region, "slot2t") || !containsID(*region, "slot3i") {
		t.Fatalf("expected hinted slot list to own real children: %#v", region.Children)
	}
	if containsID(*region, "outside") {
		t.Fatalf("hinted slot list consumed outside child: %#v", region.Children)
	}
}

func TestBuildDoesNotCreateEmptyRegionFromHintAlone(t *testing.T) {
	doc := fixtureDoc([]ir.Node{
		text("outside", 40, 720, 90, 24, "Outside"),
	})
	doc.Root.Evidence = []ir.Evidence{regionHintEvidence("det_empty", ir.RoleViewGroup, ir.BBox{X: 40, Y: 270, Width: 500, Height: 180}, 0.96)}

	out, err := Build(doc)
	if err != nil {
		t.Fatalf("Build() error = %v", err)
	}
	if countEvidence(out.Root, string(proposalHintedSlotList)) != 0 || countEvidence(out.Root, string(proposalHintedSlot)) != 0 {
		t.Fatalf("detector hint created empty region:\n%s", MarkdownReport(out))
	}
	if !containsID(out.Root, "outside") {
		t.Fatalf("ordinary child should remain in the tree")
	}
}

func TestHomeIndicatorBBoxUsesBottomInset(t *testing.T) {
	box := homeIndicatorBBox(ir.BBox{X: 0, Y: 0, Width: 665, Height: 1440})
	if box != (ir.BBox{X: 215, Y: 1418, Width: 235, Height: 8}) {
		t.Fatalf("unexpected home indicator bbox: %#v", box)
	}
}

func TestDiscardPhysicalNoiseUsesEvidenceNotesForTokenType(t *testing.T) {
	node := backgroundWithEvidence("line-bg", "solid_background", 10, 10, 90, 8)
	node.Evidence[0].Notes = "layer_background_token"
	if !discardPhysicalNoise(node) {
		t.Fatalf("expected tiny layer-background token to be discarded")
	}

	node = backgroundWithEvidence("surface-bg", "control_surface_background", 10, 10, 90, 8)
	node.Evidence[0].Notes = "surface_region_token"
	if discardPhysicalNoise(node) {
		t.Fatalf("control-surface evidence must not be discarded by evidence kind")
	}
}

func fixtureDoc(children []ir.Node) ir.Document {
	root := ir.Node{
		ID:          "root_0",
		Role:        ir.RoleRoot,
		SourceBBox:  ir.BBox{X: 0, Y: 0, Width: 665, Height: 1440},
		FigmaBBox:   ir.BBox{X: 0, Y: 0, Width: 665, Height: 1440},
		FigmaType:   ir.FigmaFrame,
		VisibleName: "Root",
		Children:    children,
		Style:       ir.Style{Visible: true, Opacity: 1},
	}
	return ir.Document{
		SchemaName: ir.SchemaName,
		Version:    ir.Version,
		Root:       root,
		Summary:    summarize(root),
	}
}

func text(id string, x, y, w, h int, value string) ir.Node {
	return ir.Node{
		ID:          id,
		Role:        ir.RoleTextView,
		SourceBBox:  ir.BBox{X: x, Y: y, Width: w, Height: h},
		FigmaBBox:   ir.BBox{X: x, Y: y, Width: w, Height: h},
		FigmaType:   ir.FigmaText,
		VisibleName: value,
		Text:        &ir.Text{Characters: value},
		Style:       ir.Style{Visible: true, Opacity: 1},
	}
}

func image(id string, x, y, w, h int) ir.Node {
	return ir.Node{
		ID:          id,
		Role:        ir.RoleImageView,
		SourceBBox:  ir.BBox{X: x, Y: y, Width: w, Height: h},
		FigmaBBox:   ir.BBox{X: x, Y: y, Width: w, Height: h},
		FigmaType:   ir.FigmaRoundedRectangle,
		VisibleName: "Image",
		Asset:       &ir.Asset{Kind: "crop"},
		Style:       ir.Style{Visible: true, Opacity: 1},
	}
}

func background(id string, x, y, w, h int) ir.Node {
	return ir.Node{
		ID:          id,
		Role:        ir.RoleBackground,
		SourceBBox:  ir.BBox{X: x, Y: y, Width: w, Height: h},
		FigmaBBox:   ir.BBox{X: x, Y: y, Width: w, Height: h},
		FigmaType:   ir.FigmaRoundedRectangle,
		VisibleName: "Background",
		Style:       ir.Style{Visible: true, Opacity: 1},
	}
}

func backgroundWithEvidence(id string, kind string, x, y, w, h int) ir.Node {
	node := background(id, x, y, w, h)
	node.Evidence = []ir.Evidence{{Kind: kind, BBox: node.SourceBBox, Confidence: 0.7, SourceID: id}}
	return node
}

func control(id string, role ir.Role, x, y, w, h int) ir.Node {
	return ir.Node{
		ID:          id,
		Role:        role,
		SourceBBox:  ir.BBox{X: x, Y: y, Width: w, Height: h},
		FigmaBBox:   ir.BBox{X: x, Y: y, Width: w, Height: h},
		FigmaType:   ir.FigmaFrame,
		VisibleName: map[ir.Role]string{ir.RoleButton: "Button", ir.RoleEditText: "Text"}[role],
		Style:       ir.Style{Visible: true, Opacity: 1},
	}
}

func regionHintEvidence(id string, role ir.Role, box ir.BBox, confidence float64) ir.Evidence {
	return ir.Evidence{
		Kind:       "assembly_region_hint",
		BBox:       box,
		Confidence: confidence,
		SourceID:   id,
		Notes:      string(role) + "/pass=layout/label=test region",
	}
}

func rootFlatLeafCount(nodes []ir.Node) int {
	count := 0
	for _, node := range nodes {
		if len(node.Children) == 0 && node.Role != ir.RoleBackground {
			count++
		}
	}
	return count
}

func firstRole(root ir.Node, role ir.Role) *ir.Node {
	if root.Role == role {
		return &root
	}
	for _, child := range root.Children {
		if found := firstRole(child, role); found != nil {
			return found
		}
	}
	return nil
}

func containsRole(root ir.Node, role ir.Role) bool {
	return firstRole(root, role) != nil
}

func backgroundsAreLate(root ir.Node) bool {
	seenBackground := false
	for _, child := range root.Children {
		if child.Role == ir.RoleBackground || child.Role == ir.RoleBgButton || child.Role == ir.RoleBgEditText {
			seenBackground = true
		} else if seenBackground {
			return false
		}
		if !backgroundsAreLate(child) {
			return false
		}
	}
	return true
}

func countEvidence(root ir.Node, kind string) int {
	count := 0
	for _, node := range flattenNodes(root) {
		if len(node.Evidence) > 0 && node.Evidence[0].Kind == kind {
			count++
		}
	}
	return count
}

func firstEvidence(root ir.Node, kind string) *ir.Node {
	if len(root.Evidence) > 0 && root.Evidence[0].Kind == kind {
		return &root
	}
	for _, child := range root.Children {
		if found := firstEvidence(child, kind); found != nil {
			return found
		}
	}
	return nil
}

func containsID(root ir.Node, id string) bool {
	if root.ID == id {
		return true
	}
	for _, child := range root.Children {
		if containsID(child, id) {
			return true
		}
	}
	return false
}

func findNode(nodes []ir.Node, id string) *ir.Node {
	for i := range nodes {
		if nodes[i].ID == id {
			return &nodes[i]
		}
	}
	return nil
}

func flattenNodes(root ir.Node) []ir.Node {
	out := []ir.Node{root}
	for _, child := range root.Children {
		out = append(out, flattenNodes(child)...)
	}
	return out
}
