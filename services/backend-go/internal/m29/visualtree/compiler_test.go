package visualtree

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/contract"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/evidence"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/relation"
)

func TestCompileBuildsLayerWithParentRelativeText(t *testing.T) {
	tmp := t.TempDir()
	tokenPath, relationPath := writeInputs(t, tmp,
		[]evidence.Token{
			token("surface", "surface_region_token", contract.BBox{X: 20, Y: 30, Width: 260, Height: 80}),
			textToken("title", contract.BBox{X: 42, Y: 52, Width: 90, Height: 20}, "Hello"),
		},
		[]relation.Relation{
			rel("rel_0001", "contains", "structural", "surface", "title"),
		},
	)

	doc, err := Compile(Options{TokenPath: tokenPath, RelationPath: relationPath, OutputDir: tmp})
	if err != nil {
		t.Fatalf("Compile() error = %v", err)
	}
	layer := doc.Root.Children[0]
	if layer.Type != "Layer" {
		t.Fatalf("expected surface to become Layer, got %#v", layer)
	}
	background := findChild(layer, "surface_background")
	if background.ID == "" || background.Type != "Image" || background.Meta.GroupKind != "background_leaf" {
		t.Fatalf("expected Codia-like background leaf first, got %#v", layer.Children)
	}
	child := findDescendant(layer, "title")
	if child.Type != "Text" {
		t.Fatalf("expected text child, got %#v", child)
	}
	group := findParentOf(layer, "title")
	if group.ID == "" || !group.Meta.Synthetic || group.Meta.GroupKind != "text_background_group" {
		t.Fatalf("expected text to be wrapped in Codia-like text background group, got %#v", layer)
	}
	if group.Layout.X != 22 || group.Layout.Y != 22 || !group.Layout.Relative {
		t.Fatalf("expected group layout relative to physical layer, got %#v", group.Layout)
	}
	if child.Layout.X != 0 || child.Layout.Y != 0 || !child.Layout.Relative {
		t.Fatalf("expected text layout relative to text background group, got %#v", child.Layout)
	}
	if child.Content.Text != "Hello" {
		t.Fatalf("expected OCR text content, got %#v", child.Content)
	}
	if doc.VisualElement.ElementType != "Body" || doc.VisualElement.ElementName != "Root" {
		t.Fatalf("expected Codia-like root visual element, got %#v", doc.VisualElement)
	}
	veLayer := doc.VisualElement.ChildElements[0]
	if veLayer.ElementType != "Layer" || veLayer.ElementName != "Groups" {
		t.Fatalf("expected physical layer as Codia-like Layer, got %#v", veLayer)
	}
	if veLayer.LayoutConfig.PositionMode != "Absolute" || veLayer.LayoutConfig.AbsoluteAttrs.Coord[0] != 20 || veLayer.LayoutConfig.AbsoluteAttrs.Coord[1] != 30 {
		t.Fatalf("expected Codia-like absolute layer coord, got %#v", veLayer.LayoutConfig)
	}
	if veLayer.StyleConfig.BackgroundSpec == nil || veLayer.StyleConfig.BackgroundSpec.Type != "IMAGE" {
		t.Fatalf("expected layer background spec, got %#v", veLayer.StyleConfig)
	}
	veTitle := findVisualElement(veLayer, "title")
	if veTitle.ElementType != "Text" || veTitle.ContentData == nil || veTitle.ContentData.TextValue != "Hello" {
		t.Fatalf("expected text contentData in visual element, got %#v", veTitle)
	}
	if veTitle.LayoutConfig.AbsoluteAttrs.Coord[0] != 0 || veTitle.LayoutConfig.AbsoluteAttrs.Coord[1] != 0 {
		t.Fatalf("expected text coord relative to text background group, got %#v", veTitle.LayoutConfig)
	}
	if _, err := os.Stat(filepath.Join(tmp, "visual_element.v1.json")); err != nil {
		t.Fatalf("expected visual_element.v1.json artifact: %v", err)
	}
}

func TestCompilePromotesRasterWithChildrenToBackgroundLayer(t *testing.T) {
	tmp := t.TempDir()
	raster := token("raster", "raster_region_token", contract.BBox{X: 10, Y: 10, Width: 300, Height: 160})
	raster.CompileHints.CanContainForeground = true
	tokenPath, relationPath := writeInputs(t, tmp,
		[]evidence.Token{
			raster,
			textToken("label", contract.BBox{X: 40, Y: 50, Width: 100, Height: 24}, "Label"),
		},
		[]relation.Relation{
			rel("rel_0001", "contains", "structural", "raster", "label"),
			rel("rel_0002", "foreground_inside_background", "structural", "label", "raster"),
		},
	)

	doc, err := Compile(Options{TokenPath: tokenPath, RelationPath: relationPath, OutputDir: tmp})
	if err != nil {
		t.Fatalf("Compile() error = %v", err)
	}
	layer := doc.Root.Children[0]
	if layer.Type != "Layer" || layer.Style.BackgroundRef != "raster" {
		t.Fatalf("expected raster background Layer, got %#v", layer)
	}
	if len(layer.Children) != 2 || layer.Children[0].Meta.GroupKind != "background_leaf" || findDescendant(layer, "label").Type != "Text" {
		t.Fatalf("raster background should not swallow foreground children: %#v", layer.Children)
	}
	if doc.Diagnostics.BackgroundLayerCount != 1 {
		t.Fatalf("expected background layer diagnostic, got %#v", doc.Diagnostics)
	}
}

func TestCompileDoesNotPromoteRasterWithoutContainCapabilityToBackgroundLayer(t *testing.T) {
	tmp := t.TempDir()
	tokenPath, relationPath := writeInputs(t, tmp,
		[]evidence.Token{
			token("raster", "raster_region_token", contract.BBox{X: 10, Y: 10, Width: 300, Height: 160}),
			textToken("label", contract.BBox{X: 40, Y: 50, Width: 100, Height: 24}, "Label"),
		},
		[]relation.Relation{
			rel("rel_0001", "contains", "structural", "raster", "label"),
			rel("rel_0002", "foreground_inside_background", "structural", "label", "raster"),
		},
	)

	doc, err := Compile(Options{TokenPath: tokenPath, RelationPath: relationPath, OutputDir: tmp})
	if err != nil {
		t.Fatalf("Compile() error = %v", err)
	}
	if len(doc.Root.Children) != 2 {
		t.Fatalf("expected raster and text to stay separate, got %#v", doc.Root.Children)
	}
	for _, child := range doc.Root.Children {
		if child.ID == "raster" && (child.Type != "Image" || child.Style.BackgroundRef != "") {
			t.Fatalf("raster without contain capability must stay Image, got %#v", child)
		}
	}
	if doc.Diagnostics.BackgroundLayerCount != 0 {
		t.Fatalf("expected no background layer diagnostic, got %#v", doc.Diagnostics)
	}
}

func TestCompileParentsContainedChildIntoPhysicalLayerByBBox(t *testing.T) {
	tmp := t.TempDir()
	tokenPath, relationPath := writeInputs(t, tmp,
		[]evidence.Token{
			token("surface", "surface_region_token", contract.BBox{X: 20, Y: 30, Width: 260, Height: 80}),
			textToken("title", contract.BBox{X: 42, Y: 52, Width: 90, Height: 20}, "Hello"),
		},
		[]relation.Relation{
			rel("rel_0001", "same_row", "layout_hint", "surface", "title"),
		},
	)

	doc, err := Compile(Options{TokenPath: tokenPath, RelationPath: relationPath, OutputDir: tmp})
	if err != nil {
		t.Fatalf("Compile() error = %v", err)
	}
	if len(doc.Root.Children) != 1 {
		t.Fatalf("expected physical containment parent, got %#v", doc.Root.Children)
	}
	layer := doc.Root.Children[0]
	if findDescendant(layer, "title").ID == "" {
		t.Fatalf("expected title under physical layer, got %#v", layer)
	}
	title := findDescendant(layer, "title")
	if title.Meta.ParentReason != "bbox_containment" {
		t.Fatalf("expected bbox containment reason, got %#v", title.Meta)
	}
	if doc.Diagnostics.ContainmentOnlyParentCount != 1 || doc.Diagnostics.ContainmentAppliedCount != 1 {
		t.Fatalf("expected containment diagnostics, got %#v", doc.Diagnostics)
	}
}

func TestCompileUsesSmallestContainingParent(t *testing.T) {
	tmp := t.TempDir()
	tokenPath, relationPath := writeInputs(t, tmp,
		[]evidence.Token{
			token("outer", "surface_region_token", contract.BBox{X: 0, Y: 0, Width: 400, Height: 300}),
			token("inner", "surface_region_token", contract.BBox{X: 40, Y: 60, Width: 200, Height: 80}),
			textToken("title", contract.BBox{X: 70, Y: 80, Width: 90, Height: 20}, "Hello"),
		},
		[]relation.Relation{
			rel("rel_0001", "contains", "structural", "outer", "inner"),
			rel("rel_0002", "contains", "structural", "outer", "title"),
			rel("rel_0003", "contains", "structural", "inner", "title"),
		},
	)

	doc, err := Compile(Options{TokenPath: tokenPath, RelationPath: relationPath, OutputDir: tmp})
	if err != nil {
		t.Fatalf("Compile() error = %v", err)
	}
	outer := doc.Root.Children[0]
	inner := findChild(outer, "inner")
	title := findDescendant(inner, "title")
	if inner.ID != "inner" || title.ID != "title" {
		t.Fatalf("expected title under smallest containing parent, got %#v", doc.Root)
	}
	group := findParentOf(inner, "title")
	if group.ID == "" || group.Layout.X != 30 || group.Layout.Y != 20 || !group.Layout.Relative {
		t.Fatalf("expected title group layout relative to inner, got group=%#v title=%#v", group, title)
	}
	if title.Layout.X != 0 || title.Layout.Y != 0 || !title.Layout.Relative {
		t.Fatalf("expected title layout relative to text background group, got %#v", title.Layout)
	}
}

func TestCompileGroupsLocalProjectionRowAsSyntheticLayer(t *testing.T) {
	tmp := t.TempDir()
	tokenPath, relationPath := writeInputs(t, tmp,
		[]evidence.Token{
			textToken("a", contract.BBox{X: 20, Y: 30, Width: 40, Height: 20}, "A"),
			textToken("b", contract.BBox{X: 64, Y: 31, Width: 40, Height: 20}, "B"),
			textToken("c", contract.BBox{X: 108, Y: 30, Width: 40, Height: 20}, "C"),
		},
		[]relation.Relation{
			rel("rel_0001", "same_row", "layout_hint", "a", "b"),
			rel("rel_0002", "same_row", "layout_hint", "b", "c"),
		},
	)

	doc, err := Compile(Options{TokenPath: tokenPath, RelationPath: relationPath, OutputDir: tmp})
	if err != nil {
		t.Fatalf("Compile() error = %v", err)
	}
	if len(doc.Root.Children) != 3 {
		t.Fatalf("single-line text without enclosing visual evidence should stay flat, got %#v", doc.Root.Children)
	}
	if doc.Diagnostics.GroupKindCounts["row_group"] != 0 {
		t.Fatalf("same_row must not create legacy row_group, got %#v", doc.Diagnostics)
	}
}

func TestCompileDoesNotGroupRowFromSameRowRelationAlone(t *testing.T) {
	tmp := t.TempDir()
	tokenPath, relationPath := writeInputs(t, tmp,
		[]evidence.Token{
			textToken("a", contract.BBox{X: 20, Y: 30, Width: 40, Height: 20}, "A"),
			textToken("b", contract.BBox{X: 64, Y: 70, Width: 40, Height: 20}, "B"),
			textToken("c", contract.BBox{X: 108, Y: 110, Width: 40, Height: 20}, "C"),
		},
		[]relation.Relation{
			rel("rel_0001", "same_row", "layout_hint", "a", "b"),
			rel("rel_0002", "same_row", "layout_hint", "b", "c"),
		},
	)

	doc, err := Compile(Options{TokenPath: tokenPath, RelationPath: relationPath, OutputDir: tmp})
	if err != nil {
		t.Fatalf("Compile() error = %v", err)
	}
	if doc.Diagnostics.SyntheticGroupCount != 0 {
		t.Fatalf("same_row relation alone must not create row group, got %#v", doc.Root)
	}
}

func TestCompileDoesNotGroupAcrossDifferentParents(t *testing.T) {
	tmp := t.TempDir()
	tokenPath, relationPath := writeInputs(t, tmp,
		[]evidence.Token{
			token("surface_a", "surface_region_token", contract.BBox{X: 0, Y: 0, Width: 160, Height: 80}),
			textToken("a1", contract.BBox{X: 10, Y: 20, Width: 30, Height: 18}, "A1"),
			textToken("a2", contract.BBox{X: 48, Y: 20, Width: 30, Height: 18}, "A2"),
			token("surface_b", "surface_region_token", contract.BBox{X: 0, Y: 100, Width: 160, Height: 80}),
			textToken("b1", contract.BBox{X: 10, Y: 120, Width: 30, Height: 18}, "B1"),
		},
		[]relation.Relation{
			rel("rel_0001", "contains", "structural", "surface_a", "a1"),
			rel("rel_0002", "contains", "structural", "surface_a", "a2"),
			rel("rel_0003", "contains", "structural", "surface_b", "b1"),
			rel("rel_0004", "same_row", "layout_hint", "a1", "a2"),
			rel("rel_0005", "same_row", "layout_hint", "a2", "b1"),
		},
	)

	doc, err := Compile(Options{TokenPath: tokenPath, RelationPath: relationPath, OutputDir: tmp})
	if err != nil {
		t.Fatalf("Compile() error = %v", err)
	}
	if doc.Diagnostics.GroupKindCounts["row_group"] != 0 {
		t.Fatalf("same_row across different parents must not create legacy row group, got %#v", doc.Root)
	}
}

func TestCompileLetsSyntheticLayerParentContainedChildByBBox(t *testing.T) {
	tmp := t.TempDir()
	tokenPath, relationPath := writeInputs(t, tmp,
		[]evidence.Token{
			textToken("a", contract.BBox{X: 20, Y: 30, Width: 40, Height: 20}, "A"),
			textToken("b", contract.BBox{X: 64, Y: 31, Width: 40, Height: 20}, "B"),
			textToken("c", contract.BBox{X: 108, Y: 30, Width: 40, Height: 20}, "C"),
			textToken("orphan", contract.BBox{X: 70, Y: 32, Width: 20, Height: 12}, "O"),
		},
		[]relation.Relation{
			rel("rel_0001", "same_row", "layout_hint", "a", "b"),
			rel("rel_0002", "same_row", "layout_hint", "b", "c"),
		},
	)

	doc, err := Compile(Options{TokenPath: tokenPath, RelationPath: relationPath, OutputDir: tmp})
	if err != nil {
		t.Fatalf("Compile() error = %v", err)
	}
	var group Node
	for _, child := range doc.Root.Children {
		if child.Meta.Synthetic && child.Meta.GroupKind == "spatial_group" {
			group = child
		}
	}
	if group.ID == "" || findChild(group, "orphan").ID == "" {
		t.Fatalf("expected bbox-overlapped text to be grouped by spatial clustering, got %#v", doc.Root.Children)
	}
}

func TestCompileCompletesRowGroupWithLocalProjectionSibling(t *testing.T) {
	tmp := t.TempDir()
	tokenPath, relationPath := writeInputs(t, tmp,
		[]evidence.Token{
			textToken("a", contract.BBox{X: 20, Y: 30, Width: 40, Height: 20}, "A"),
			textToken("b", contract.BBox{X: 64, Y: 31, Width: 40, Height: 20}, "B"),
			textToken("c", contract.BBox{X: 108, Y: 30, Width: 40, Height: 20}, "C"),
			textToken("d", contract.BBox{X: 156, Y: 31, Width: 40, Height: 20}, "D"),
		},
		[]relation.Relation{
			rel("rel_0001", "same_row", "layout_hint", "a", "b"),
			rel("rel_0002", "same_row", "layout_hint", "b", "c"),
			rel("rel_0003", "same_row", "layout_hint", "c", "d"),
		},
	)

	doc, err := Compile(Options{TokenPath: tokenPath, RelationPath: relationPath, OutputDir: tmp})
	if err != nil {
		t.Fatalf("Compile() error = %v", err)
	}
	group := doc.Root.Children[0]
	if !group.Meta.Synthetic || group.Meta.GroupKind != "spatial_group" || len(group.Children) != 3 {
		t.Fatalf("expected local spatial group, got %#v", group)
	}
}

func TestCompileDoesNotCreateRowGroupForMultiLineMixedRegion(t *testing.T) {
	tmp := t.TempDir()
	tokenPath, relationPath := writeInputs(t, tmp,
		[]evidence.Token{
			token("left_raster", "raster_region_token", contract.BBox{X: 145, Y: 186, Width: 386, Height: 177}),
			token("right_raster", "raster_region_token", contract.BBox{X: 470, Y: 186, Width: 360, Height: 349}),
			textToken("headline", contract.BBox{X: 57, Y: 288, Width: 328, Height: 66}, "headline"),
			textToken("subhead", contract.BBox{X: 59, Y: 359, Width: 270, Height: 60}, "subhead"),
			token("symbol", "symbol_cluster_token", contract.BBox{X: 316, Y: 356, Width: 198, Height: 125}),
		},
		[]relation.Relation{
			rel("rel_0001", "same_row", "layout_hint", "left_raster", "right_raster"),
			rel("rel_0002", "same_row", "layout_hint", "headline", "left_raster"),
			rel("rel_0003", "same_row", "layout_hint", "subhead", "symbol"),
		},
	)

	doc, err := Compile(Options{TokenPath: tokenPath, RelationPath: relationPath, OutputDir: tmp})
	if err != nil {
		t.Fatalf("Compile() error = %v", err)
	}
	if doc.Diagnostics.GroupKindCounts["row_group"] != 0 {
		t.Fatalf("multi-line mixed region must not become row_group, got %#v", doc.Root)
	}
}

func TestCompileDoesNotCreateRowGroupForThinLineFragments(t *testing.T) {
	tmp := t.TempDir()
	tokenPath, relationPath := writeInputs(t, tmp,
		[]evidence.Token{
			token("line_a", "line_token", contract.BBox{X: 79, Y: 1587, Width: 57, Height: 2}),
			token("line_b", "line_token", contract.BBox{X: 138, Y: 1587, Width: 61, Height: 2}),
			token("line_c", "line_token", contract.BBox{X: 200, Y: 1587, Width: 101, Height: 2}),
		},
		[]relation.Relation{
			rel("rel_0001", "same_row", "layout_hint", "line_a", "line_b"),
			rel("rel_0002", "same_row", "layout_hint", "line_b", "line_c"),
		},
	)

	doc, err := Compile(Options{TokenPath: tokenPath, RelationPath: relationPath, OutputDir: tmp})
	if err != nil {
		t.Fatalf("Compile() error = %v", err)
	}
	if doc.Diagnostics.SyntheticGroupCount != 0 {
		t.Fatalf("thin line fragments must not create row group, got %#v", doc.Root)
	}
}

func TestCompileKeepsSyntheticGroupBBoxStableAfterContainment(t *testing.T) {
	tmp := t.TempDir()
	tokenPath, relationPath := writeInputs(t, tmp,
		[]evidence.Token{
			textToken("a", contract.BBox{X: 60, Y: 30, Width: 40, Height: 20}, "A"),
			textToken("b", contract.BBox{X: 104, Y: 31, Width: 40, Height: 20}, "B"),
			textToken("c", contract.BBox{X: 148, Y: 30, Width: 40, Height: 20}, "C"),
			textToken("left", contract.BBox{X: 10, Y: 31, Width: 40, Height: 20}, "L"),
		},
		[]relation.Relation{
			rel("rel_0001", "same_row", "layout_hint", "a", "b"),
			rel("rel_0002", "same_row", "layout_hint", "b", "c"),
			rel("rel_0003", "same_row", "layout_hint", "left", "a"),
		},
	)

	doc, err := Compile(Options{TokenPath: tokenPath, RelationPath: relationPath, OutputDir: tmp})
	if err != nil {
		t.Fatalf("Compile() error = %v", err)
	}
	group := doc.Root.Children[0]
	if group.BBox.X != 10 {
		t.Fatalf("expected group bbox to include row members, got %#v", group.BBox)
	}
	for _, child := range group.Children {
		if child.Layout.X < 0 || child.Layout.Y < 0 {
			t.Fatalf("child layout should not be negative after bbox recompute: %#v in %#v", child, group)
		}
	}
}

func TestCompileDoesNotCreateSemanticNodeTypes(t *testing.T) {
	tmp := t.TempDir()
	tokenPath, relationPath := writeInputs(t, tmp,
		[]evidence.Token{
			textToken("a", contract.BBox{X: 20, Y: 30, Width: 40, Height: 20}, "A"),
			textToken("b", contract.BBox{X: 64, Y: 31, Width: 40, Height: 20}, "B"),
			textToken("c", contract.BBox{X: 108, Y: 30, Width: 40, Height: 20}, "C"),
		},
		[]relation.Relation{
			rel("rel_0001", "same_row", "layout_hint", "a", "b"),
			rel("rel_0002", "same_row", "layout_hint", "b", "c"),
		},
	)

	doc, err := Compile(Options{TokenPath: tokenPath, RelationPath: relationPath, OutputDir: tmp})
	if err != nil {
		t.Fatalf("Compile() error = %v", err)
	}
	allowed := map[string]bool{"Body": true, "Layer": true, "Text": true, "Image": true}
	for nodeType := range doc.Diagnostics.NodeTypeCounts {
		if !allowed[nodeType] {
			t.Fatalf("unexpected semantic node type %q in %#v", nodeType, doc.Diagnostics.NodeTypeCounts)
		}
	}
}

func writeInputs(t *testing.T, dir string, tokens []evidence.Token, relations []relation.Relation) (string, string) {
	t.Helper()
	tokenPath := filepath.Join(dir, "evidence_tokens.v1.json")
	relationPath := filepath.Join(dir, "relation_graph.v1.json")
	writeJSON(t, tokenPath, evidence.Document{
		SchemaName: "M29EvidenceTokens",
		Version:    "1.0",
		Source: evidence.Source{
			ImageWidth:  400,
			ImageHeight: 300,
		},
		Tokens: tokens,
	})
	writeJSON(t, relationPath, relation.Document{
		SchemaName: "M29RelationGraph",
		Version:    "1.1",
		Relations:  relations,
	})
	return tokenPath, relationPath
}

func token(id string, tokenType string, bbox contract.BBox) evidence.Token {
	return evidence.Token{
		ID:          id,
		TokenType:   tokenType,
		BBox:        bbox,
		Disposition: "main",
	}
}

func textToken(id string, bbox contract.BBox, text string) evidence.Token {
	item := token(id, "text_token", bbox)
	item.Content.Text = text
	return item
}

func rel(id string, relationType string, category string, from string, to string) relation.Relation {
	return relation.Relation{
		ID:           id,
		RelationType: relationType,
		Category:     category,
		FromID:       from,
		ToID:         to,
		Confidence:   0.9,
		Strength:     "strong",
	}
}

func findChild(parent Node, id string) Node {
	for _, child := range parent.Children {
		if child.ID == id {
			return child
		}
	}
	return Node{}
}

func findDescendant(parent Node, id string) Node {
	for _, child := range parent.Children {
		if child.ID == id {
			return child
		}
		if found := findDescendant(child, id); found.ID != "" {
			return found
		}
	}
	return Node{}
}

func findParentOf(parent Node, id string) Node {
	for _, child := range parent.Children {
		if child.ID == id {
			return parent
		}
		if found := findParentOf(child, id); found.ID != "" {
			return found
		}
	}
	return Node{}
}

func findVisualElement(parent VisualElement, id string) VisualElement {
	if parent.ElementID == id {
		return parent
	}
	for _, child := range parent.ChildElements {
		if found := findVisualElement(child, id); found.ElementID != "" {
			return found
		}
	}
	return VisualElement{}
}

func writeJSON(t *testing.T, path string, value any) {
	t.Helper()
	data, err := json.Marshal(value)
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, data, 0o644); err != nil {
		t.Fatal(err)
	}
}
