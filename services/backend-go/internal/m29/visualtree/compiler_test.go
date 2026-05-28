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
	child := layer.Children[0]
	if child.Type != "Text" {
		t.Fatalf("expected text child, got %#v", child)
	}
	if child.Layout.X != 22 || child.Layout.Y != 22 || !child.Layout.Relative {
		t.Fatalf("expected parent-relative child layout, got %#v", child.Layout)
	}
	if child.Content.Text != "Hello" {
		t.Fatalf("expected OCR text content, got %#v", child.Content)
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
	if len(layer.Children) != 1 || layer.Children[0].Type != "Text" {
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
	if len(layer.Children) != 1 || layer.Children[0].ID != "title" {
		t.Fatalf("expected title under physical layer, got %#v", layer)
	}
	if layer.Children[0].Meta.ParentReason != "bbox_containment" {
		t.Fatalf("expected bbox containment reason, got %#v", layer.Children[0].Meta)
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
	inner := outer.Children[0]
	if inner.ID != "inner" || len(inner.Children) != 1 || inner.Children[0].ID != "title" {
		t.Fatalf("expected title under smallest containing parent, got %#v", doc.Root)
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
	if len(doc.Root.Children) != 1 {
		t.Fatalf("expected row group under body, got %#v", doc.Root.Children)
	}
	group := doc.Root.Children[0]
	if group.Type != "Layer" || !group.Meta.Synthetic || group.Meta.GroupKind != "row_group" {
		t.Fatalf("expected synthetic row Layer, got %#v", group)
	}
	if len(group.Children) != 3 {
		t.Fatalf("expected three row children, got %#v", group.Children)
	}
	if group.Children[0].Type != "Text" || group.Children[0].Layout.X != 0 || !group.Children[0].Layout.Relative {
		t.Fatalf("expected relative text child in group, got %#v", group.Children[0])
	}
	if doc.Diagnostics.SyntheticGroupCount != 1 || doc.Diagnostics.GroupKindCounts["row_group"] != 1 {
		t.Fatalf("expected group diagnostics, got %#v", doc.Diagnostics)
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
	if doc.Diagnostics.SyntheticGroupCount != 0 {
		t.Fatalf("same_row across different parents must not create group, got %#v", doc.Root)
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
	if len(doc.Root.Children) != 1 {
		t.Fatalf("expected synthetic layer under body, got %#v", doc.Root.Children)
	}
	group := doc.Root.Children[0]
	if !group.Meta.Synthetic || group.Meta.GroupKind != "row_group" {
		t.Fatalf("expected synthetic row layer, got %#v", group)
	}
	if len(group.Children) != 4 {
		t.Fatalf("expected contained orphan to be parented by synthetic layer, got %#v", group)
	}
	var orphan Node
	for _, child := range group.Children {
		if child.ID == "orphan" {
			orphan = child
		}
	}
	if orphan.ID == "" || orphan.Meta.ParentReason != "bbox_containment" {
		t.Fatalf("expected orphan bbox containment parent reason, got %#v", orphan)
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
	if len(group.Children) != 4 {
		t.Fatalf("expected completed row group, got %#v", group)
	}
}

func TestCompileDoesNotCreateRowGroupForMultiLineBanner(t *testing.T) {
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
		t.Fatalf("multi-line banner must not become row_group, got %#v", doc.Root)
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

func TestCompileGroupsMultiRowMatrixAsAxisProjectionGroup(t *testing.T) {
	tmp := t.TempDir()
	tokenPath, relationPath := writeInputs(t, tmp,
		[]evidence.Token{
			textToken("a1", contract.BBox{X: 20, Y: 30, Width: 40, Height: 20}, "A1"),
			textToken("a2", contract.BBox{X: 100, Y: 30, Width: 40, Height: 20}, "A2"),
			textToken("b1", contract.BBox{X: 20, Y: 70, Width: 40, Height: 20}, "B1"),
			textToken("b2", contract.BBox{X: 100, Y: 70, Width: 40, Height: 20}, "B2"),
		},
		[]relation.Relation{
			rel("rel_0001", "same_column", "layout_hint", "a1", "b1"),
			rel("rel_0002", "same_column", "layout_hint", "a2", "b2"),
		},
	)

	doc, err := Compile(Options{TokenPath: tokenPath, RelationPath: relationPath, OutputDir: tmp})
	if err != nil {
		t.Fatalf("Compile() error = %v", err)
	}
	if len(doc.Root.Children) != 1 {
		t.Fatalf("expected axis projection group under body, got %#v", doc.Root.Children)
	}
	group := doc.Root.Children[0]
	if group.Type != "Layer" || !group.Meta.Synthetic || group.Meta.GroupKind != "axis_projection_group" {
		t.Fatalf("expected axis projection Layer, got %#v", group)
	}
	if len(group.Children) != 4 || group.BBox.X != 20 || group.BBox.Y != 30 || group.BBox.Width != 120 || group.BBox.Height != 60 {
		t.Fatalf("expected stable union bbox and children, got %#v", group)
	}
	if group.Children[0].Layout.X != 0 || group.Children[0].Layout.Y != 0 || !group.Children[0].Layout.Relative {
		t.Fatalf("expected parent-relative child layout, got %#v", group.Children[0])
	}
	if doc.Diagnostics.GroupKindCounts["axis_projection_group"] != 1 {
		t.Fatalf("expected axis projection diagnostics, got %#v", doc.Diagnostics)
	}
}

func TestCompileWrapsMultipleRowGroupsAsAxisProjectionGroup(t *testing.T) {
	tmp := t.TempDir()
	tokenPath, relationPath := writeInputs(t, tmp,
		[]evidence.Token{
			textToken("a1", contract.BBox{X: 20, Y: 30, Width: 30, Height: 18}, "A1"),
			textToken("a2", contract.BBox{X: 70, Y: 30, Width: 30, Height: 18}, "A2"),
			textToken("a3", contract.BBox{X: 120, Y: 30, Width: 30, Height: 18}, "A3"),
			textToken("b1", contract.BBox{X: 20, Y: 70, Width: 30, Height: 18}, "B1"),
			textToken("b2", contract.BBox{X: 70, Y: 70, Width: 30, Height: 18}, "B2"),
			textToken("b3", contract.BBox{X: 120, Y: 70, Width: 30, Height: 18}, "B3"),
		},
		[]relation.Relation{},
	)

	doc, err := Compile(Options{TokenPath: tokenPath, RelationPath: relationPath, OutputDir: tmp})
	if err != nil {
		t.Fatalf("Compile() error = %v", err)
	}
	if len(doc.Root.Children) != 1 {
		t.Fatalf("expected one axis projection group, got %#v", doc.Root.Children)
	}
	group := doc.Root.Children[0]
	if group.Meta.GroupKind != "axis_projection_group" || len(group.Children) != 2 {
		t.Fatalf("expected axis projection wrapping two row groups, got %#v", group)
	}
	for _, row := range group.Children {
		if row.Meta.GroupKind != "row_group" || len(row.Children) != 3 {
			t.Fatalf("expected row group child, got %#v", row)
		}
	}
	if doc.Diagnostics.GroupKindCounts["row_group"] != 2 || doc.Diagnostics.GroupKindCounts["axis_projection_group"] != 1 {
		t.Fatalf("expected row+axis diagnostics, got %#v", doc.Diagnostics)
	}
}

func TestCompileDoesNotCreateAxisProjectionFromRelationHintsAlone(t *testing.T) {
	tmp := t.TempDir()
	tokenPath, relationPath := writeInputs(t, tmp,
		[]evidence.Token{
			textToken("a1", contract.BBox{X: 20, Y: 30, Width: 40, Height: 20}, "A1"),
			textToken("a2", contract.BBox{X: 120, Y: 85, Width: 40, Height: 20}, "A2"),
			textToken("b1", contract.BBox{X: 20, Y: 190, Width: 40, Height: 20}, "B1"),
			textToken("b2", contract.BBox{X: 120, Y: 245, Width: 40, Height: 20}, "B2"),
		},
		[]relation.Relation{
			rel("rel_0001", "same_column", "layout_hint", "a1", "b1"),
			rel("rel_0002", "same_column", "layout_hint", "a2", "b2"),
		},
	)

	doc, err := Compile(Options{TokenPath: tokenPath, RelationPath: relationPath, OutputDir: tmp})
	if err != nil {
		t.Fatalf("Compile() error = %v", err)
	}
	if doc.Diagnostics.GroupKindCounts["axis_projection_group"] != 0 {
		t.Fatalf("relation hints alone must not create axis projection group, got %#v", doc.Root)
	}
}

func TestCompileDoesNotCreateAxisProjectionForMultiLineBanner(t *testing.T) {
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
			rel("rel_0001", "same_column", "layout_hint", "headline", "subhead"),
			rel("rel_0002", "same_column", "layout_hint", "left_raster", "right_raster"),
		},
	)

	doc, err := Compile(Options{TokenPath: tokenPath, RelationPath: relationPath, OutputDir: tmp})
	if err != nil {
		t.Fatalf("Compile() error = %v", err)
	}
	if doc.Diagnostics.GroupKindCounts["axis_projection_group"] != 0 {
		t.Fatalf("multi-line banner must not become axis projection group, got %#v", doc.Root)
	}
}

func TestCompileDoesNotCreateAxisProjectionAcrossLargeVerticalGap(t *testing.T) {
	tmp := t.TempDir()
	tokenPath, relationPath := writeInputs(t, tmp,
		[]evidence.Token{
			textToken("a1", contract.BBox{X: 20, Y: 20, Width: 40, Height: 20}, "A1"),
			textToken("a2", contract.BBox{X: 100, Y: 20, Width: 40, Height: 20}, "A2"),
			textToken("b1", contract.BBox{X: 20, Y: 220, Width: 40, Height: 20}, "B1"),
			textToken("b2", contract.BBox{X: 100, Y: 220, Width: 40, Height: 20}, "B2"),
		},
		[]relation.Relation{
			rel("rel_0001", "same_column", "layout_hint", "a1", "b1"),
			rel("rel_0002", "same_column", "layout_hint", "a2", "b2"),
		},
	)

	doc, err := Compile(Options{TokenPath: tokenPath, RelationPath: relationPath, OutputDir: tmp})
	if err != nil {
		t.Fatalf("Compile() error = %v", err)
	}
	if doc.Diagnostics.GroupKindCounts["axis_projection_group"] != 0 {
		t.Fatalf("large vertical gap must not create axis projection group, got %#v", doc.Root)
	}
}

func TestCompileDoesNotCreateAxisProjectionForThinLineFragments(t *testing.T) {
	tmp := t.TempDir()
	tokenPath, relationPath := writeInputs(t, tmp,
		[]evidence.Token{
			token("line_a", "line_token", contract.BBox{X: 20, Y: 30, Width: 80, Height: 2}),
			token("line_b", "line_token", contract.BBox{X: 120, Y: 30, Width: 80, Height: 2}),
			token("line_c", "line_token", contract.BBox{X: 20, Y: 70, Width: 80, Height: 2}),
			token("line_d", "line_token", contract.BBox{X: 120, Y: 70, Width: 80, Height: 2}),
		},
		[]relation.Relation{},
	)

	doc, err := Compile(Options{TokenPath: tokenPath, RelationPath: relationPath, OutputDir: tmp})
	if err != nil {
		t.Fatalf("Compile() error = %v", err)
	}
	if doc.Diagnostics.SyntheticGroupCount != 0 {
		t.Fatalf("thin line fragments must not create synthetic groups, got %#v", doc.Root)
	}
}

func TestCompileAxisProjectionDoesNotPromoteRasterWithoutContainCapability(t *testing.T) {
	tmp := t.TempDir()
	tokenPath, relationPath := writeInputs(t, tmp,
		[]evidence.Token{
			token("raster", "raster_region_token", contract.BBox{X: 20, Y: 20, Width: 80, Height: 60}),
			textToken("a2", contract.BBox{X: 120, Y: 30, Width: 40, Height: 20}, "A2"),
			textToken("b1", contract.BBox{X: 20, Y: 90, Width: 40, Height: 20}, "B1"),
			textToken("b2", contract.BBox{X: 120, Y: 90, Width: 40, Height: 20}, "B2"),
		},
		[]relation.Relation{},
	)

	doc, err := Compile(Options{TokenPath: tokenPath, RelationPath: relationPath, OutputDir: tmp})
	if err != nil {
		t.Fatalf("Compile() error = %v", err)
	}
	for _, child := range flattenForTest(doc.Root) {
		if child.ID == "raster" && (child.Type != "Image" || child.Style.BackgroundRef != "") {
			t.Fatalf("raster without contain capability must stay Image, got %#v", child)
		}
	}
	if doc.Diagnostics.BackgroundLayerCount != 0 {
		t.Fatalf("axis projection must not authorize background layer, got %#v", doc.Diagnostics)
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

func flattenForTest(root Node) []Node {
	var out []Node
	var walk func(Node)
	walk = func(node Node) {
		out = append(out, node)
		for _, child := range node.Children {
			walk(child)
		}
	}
	walk(root)
	return out
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
