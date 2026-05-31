package materialize

import (
	"fmt"
	"image"
	"image/color"
	"image/png"
	"os"
	"sort"
	"strings"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/image/geometry"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/layoutir/contract"
)

type Options struct{}

type builder struct {
	doc        contract.Document
	bounds     geometry.Rect
	source     image.Image
	textItems  []contract.Evidence
	substrates []geometry.Rect
	assets     []contract.Asset
	decisions  []contract.Decision
	seq        int
}

func Build(doc contract.Document, _ Options) contract.Document {
	b := builder{
		doc:    doc,
		bounds: geometry.Rect{Width: doc.SourceImage.Width, Height: doc.SourceImage.Height},
	}
	b.source = decodeSource(doc.SourceImage.Path)
	b.doc.Root.Style.Fill = b.samplePageFill()
	b.textItems = textEvidence(doc.Evidence)
	for _, item := range sortedEvidence(doc.Evidence) {
		b.materialize(item)
	}
	b.doc.Assets = append(b.doc.Assets, b.assets...)
	b.doc.Decisions = append(b.doc.Decisions, b.decisions...)
	return b.doc
}

func (b *builder) materialize(item contract.Evidence) {
	role := canonicalRole(item.RoleHint)
	switch role {
	case "text":
		b.emitText(item)
	case "icon":
		b.emitRaster(item, contract.NodeIcon, "materialize_compact_icon")
	case "image":
		b.emitImageIfUseful(item)
	case "shape", "line":
		b.emitShape(item, role)
	case "texture_fragment", "unknown":
		b.suppress(item, "materialize_unresolved_non_structural_evidence", 0.35)
	default:
		b.suppress(item, "materialize_semantic_hint_only", item.Confidence)
	}
}

func (b *builder) emitText(item contract.Evidence) {
	text := strings.TrimSpace(item.Meta["text"])
	if text == "" {
		b.suppress(item, "materialize_empty_text_suppressed", 0.2)
		return
	}
	node := b.node(item, contract.NodeText, "Text", "editable_text")
	node.Text = &contract.Text{Characters: text}
	node.Style.Fill = b.sampleTextFill(item.BBox)
	node.Meta = map[string]string{"materializedFrom": "text_evidence"}
	if b.insideSubstrate(item.BBox) {
		b.emitTextEraser(item)
	}
	b.insert(node)
	b.decide(contract.DecisionPromoteText, node.ID, "materialize_text_evidence", item, item.Confidence)
}

func (b *builder) emitTextEraser(item contract.Evidence) {
	box := geometry.Clamp(expand(item.BBox, maxInt(1, item.BBox.Height/8)), b.bounds)
	if box.Empty() {
		return
	}
	node := b.node(item, contract.NodeShape, "Text Eraser", "substrate_text_eraser")
	node.BBox = box
	node.Style.Fill = b.sampleSurroundingFill(item.BBox)
	node.SemanticTags = append(node.SemanticTags, "text_eraser")
	node.Meta = map[string]string{
		"materializedFrom": "substrate_text_eraser",
		"zLayer":           "text_eraser",
	}
	b.insert(node)
	b.decide(contract.DecisionEmit, node.ID, "materialize_text_eraser_for_substrate", item, item.Confidence*0.85)
}

func (b *builder) emitImageIfUseful(item contract.Evidence) {
	if fullPageBacking(b.bounds, item.BBox) {
		b.suppress(item, "materialize_full_page_raster_suppressed", 0.2)
		return
	}
	areaRatio := ratio(item.BBox.Area(), b.bounds.Area())
	textCount := b.textsInside(item.BBox, 0.78)
	if textCount >= 2 && areaRatio > 0.08 {
		b.emitRaster(item, contract.NodeUnknownCrop, "materialize_text_bearing_raster_as_substrate")
		return
	}
	if !compactMedia(item.BBox, b.bounds) && textCount > 0 {
		b.emitRaster(item, contract.NodeUnknownCrop, "materialize_non_compact_raster_as_substrate")
		return
	}
	if structuralBand(item.BBox, b.bounds) {
		b.emitRaster(item, contract.NodeUnknownCrop, "materialize_structural_band_raster_as_substrate")
		return
	}
	b.emitRaster(item, contract.NodeImage, "materialize_image_crop")
}

func (b *builder) emitRaster(item contract.Evidence, nodeType contract.NodeType, reason string) {
	if item.BBox.Area() <= 0 || geometry.IoA(item.BBox, b.bounds) < 1 {
		b.suppress(item, "materialize_invalid_raster_bbox_suppressed", 0.1)
		return
	}
	node := b.node(item, nodeType, string(nodeType), "crop_asset")
	assetID := "asset_" + node.ID
	node.AssetRef = &contract.AssetRef{AssetID: assetID}
	node.Meta = map[string]string{"materializedFrom": "raster_evidence"}
	b.assets = append(b.assets, contract.Asset{
		ID:         assetID,
		Type:       "image",
		Format:     "png",
		BBox:       item.BBox,
		Width:      item.BBox.Width,
		Height:     item.BBox.Height,
		SourceRefs: sourceRefs(item, "asset_crop"),
	})
	if nodeType == contract.NodeUnknownCrop {
		b.substrates = append(b.substrates, item.BBox)
	}
	b.insert(node)
	state := contract.DecisionPromoteImage
	if nodeType == contract.NodeUnknownCrop {
		state = contract.DecisionFallbackCrop
	}
	b.decide(state, node.ID, reason, item, item.Confidence)
}

func (b *builder) emitShape(item contract.Evidence, role string) {
	if item.Source == "vision" {
		b.suppress(item, "materialize_vision_region_hint_only", item.Confidence)
		return
	}
	if fullPageBacking(b.bounds, item.BBox) {
		b.suppress(item, "materialize_full_page_shape_suppressed", 0.2)
		return
	}
	minArea := maxInt(8, b.bounds.Area()/250000)
	if item.BBox.Area() < minArea {
		b.suppress(item, "materialize_micro_shape_suppressed", item.Confidence*0.5)
		return
	}
	if microFragment(item.BBox, b.bounds) {
		b.suppress(item, "materialize_micro_fragment_suppressed", item.Confidence*0.5)
		return
	}
	node := b.node(item, contract.NodeShape, "Shape", "vector_shape")
	node.Style.Fill = b.sampleFill(item.BBox)
	if role == "line" {
		node.SemanticTags = append(node.SemanticTags, "line")
	}
	node.Meta = map[string]string{"materializedFrom": role + "_evidence"}
	b.insert(node)
	b.decide(contract.DecisionEmit, node.ID, "materialize_shape_evidence", item, item.Confidence)
}

func (b *builder) node(item contract.Evidence, nodeType contract.NodeType, namePrefix string, fallback string) contract.Node {
	b.seq++
	id := fmt.Sprintf("leaf_%04d", b.seq)
	return contract.Node{
		ID:             id,
		Type:           nodeType,
		Name:           fmt.Sprintf("%s %04d", namePrefix, b.seq),
		BBox:           item.BBox,
		Layout:         contract.Layout{Mode: contract.LayoutAbsolute},
		SourceRefs:     sourceRefs(item, "materialized_leaf"),
		Confidence:     item.Confidence,
		FallbackPolicy: fallback,
	}
}

func (b *builder) insert(node contract.Node) {
	insertIntoBestContainer(&b.doc.Root, node)
}

func insertIntoBestContainer(parent *contract.Node, leaf contract.Node) {
	best := -1
	bestScore := -1.0
	bestArea := 0
	for i := range parent.Children {
		child := parent.Children[i]
		if !structural(child.Type) {
			continue
		}
		score := containerScore(child.BBox, leaf.BBox)
		if score <= 0 {
			continue
		}
		area := child.BBox.Area()
		if best < 0 || score > bestScore || (score == bestScore && area < bestArea) {
			best = i
			bestScore = score
			bestArea = area
		}
	}
	if best >= 0 {
		insertIntoBestContainer(&parent.Children[best], leaf)
		return
	}
	parent.Children = append(parent.Children, leaf)
}

func containerScore(container geometry.Rect, leaf geometry.Rect) float64 {
	ioa := geometry.IoA(leaf, container)
	if centerInside(container, leaf) {
		return 2 + ioa
	}
	if ioa >= 0.50 {
		return ioa
	}
	return 0
}

func structural(value contract.NodeType) bool {
	switch value {
	case contract.NodePage, contract.NodeSection, contract.NodeRow, contract.NodeColumn, contract.NodeGroup, contract.NodeOverlay:
		return true
	default:
		return false
	}
}

func (b *builder) decide(state contract.DecisionState, nodeID string, reason string, item contract.Evidence, score float64) {
	b.decisions = append(b.decisions, contract.Decision{
		ID:         fmt.Sprintf("decision_materialize_%04d", len(b.decisions)+1),
		State:      state,
		NodeID:     nodeID,
		Reason:     reason,
		SourceRefs: sourceRefs(item, "decision_source"),
		Score:      score,
	})
}

func (b *builder) suppress(item contract.Evidence, reason string, score float64) {
	b.decide(contract.DecisionSuppress, "", reason, item, score)
}

func (b *builder) textsInside(box geometry.Rect, threshold float64) int {
	count := 0
	for _, item := range b.textItems {
		if geometry.IoA(item.BBox, box) >= threshold {
			count++
		}
	}
	return count
}

func (b *builder) insideSubstrate(box geometry.Rect) bool {
	for _, substrate := range b.substrates {
		if geometry.IoA(box, substrate) >= 0.80 {
			return true
		}
	}
	return false
}

func (b *builder) sampleFill(box geometry.Rect) string {
	if b.source == nil {
		return "#eeeeee"
	}
	bounds := b.source.Bounds()
	clamped := geometry.Clamp(box, geometry.Rect{
		X:      bounds.Min.X,
		Y:      bounds.Min.Y,
		Width:  bounds.Dx(),
		Height: bounds.Dy(),
	})
	if clamped.Empty() {
		return "#eeeeee"
	}
	stepX := maxInt(1, clamped.Width/8)
	stepY := maxInt(1, clamped.Height/8)
	var r, g, bl uint64
	count := uint64(0)
	for y := clamped.Y; y < clamped.Bottom(); y += stepY {
		for x := clamped.X; x < clamped.Right(); x += stepX {
			cr, cg, cb, _ := rgba8(b.source.At(x, y))
			r += uint64(cr)
			g += uint64(cg)
			bl += uint64(cb)
			count++
		}
	}
	if count == 0 {
		return "#eeeeee"
	}
	return fmt.Sprintf("#%02x%02x%02x", r/count, g/count, bl/count)
}

func (b *builder) samplePageFill() string {
	if b.source == nil {
		return "#f7f7f7"
	}
	bounds := b.source.Bounds()
	width := bounds.Dx()
	height := bounds.Dy()
	if width <= 0 || height <= 0 {
		return "#f7f7f7"
	}
	step := maxInt(1, minInt(width, height)/32)
	buckets := map[string]int{}
	add := func(x int, y int) {
		r, g, bl, _ := rgba8(b.source.At(bounds.Min.X+x, bounds.Min.Y+y))
		key := fmt.Sprintf("#%02x%02x%02x", quantize(r), quantize(g), quantize(bl))
		buckets[key]++
	}
	for x := 0; x < width; x += step {
		add(x, 0)
		add(x, height-1)
	}
	for y := 0; y < height; y += step {
		add(0, y)
		add(width-1, y)
	}
	best := "#f7f7f7"
	bestCount := -1
	for key, count := range buckets {
		if count > bestCount {
			best = key
			bestCount = count
		}
	}
	return best
}

func (b *builder) sampleTextFill(box geometry.Rect) string {
	if b.source == nil {
		return "#111111"
	}
	bounds := b.source.Bounds()
	imageBounds := geometry.Rect{
		X:      bounds.Min.X,
		Y:      bounds.Min.Y,
		Width:  bounds.Dx(),
		Height: bounds.Dy(),
	}
	outer := geometry.Clamp(expand(box, maxInt(2, box.Height/2)), imageBounds)
	inner := geometry.Clamp(box, imageBounds)
	if outer.Empty() || inner.Empty() {
		return "#111111"
	}
	bg := averageLuma(b.source, outer, inner)
	if bg < 128 {
		return "#f7f7f7"
	}
	return "#151515"
}

func (b *builder) sampleSurroundingFill(box geometry.Rect) string {
	if b.source == nil {
		return "#eeeeee"
	}
	bounds := b.source.Bounds()
	imageBounds := geometry.Rect{
		X:      bounds.Min.X,
		Y:      bounds.Min.Y,
		Width:  bounds.Dx(),
		Height: bounds.Dy(),
	}
	outer := geometry.Clamp(expand(box, maxInt(3, box.Height/2)), imageBounds)
	inner := geometry.Clamp(box, imageBounds)
	if outer.Empty() || inner.Empty() {
		return "#eeeeee"
	}
	stepX := maxInt(1, outer.Width/10)
	stepY := maxInt(1, outer.Height/10)
	var r, g, bl uint64
	count := uint64(0)
	for y := outer.Y; y < outer.Bottom(); y += stepY {
		for x := outer.X; x < outer.Right(); x += stepX {
			if x >= inner.X && x < inner.Right() && y >= inner.Y && y < inner.Bottom() {
				continue
			}
			cr, cg, cb, _ := rgba8(b.source.At(x, y))
			r += uint64(cr)
			g += uint64(cg)
			bl += uint64(cb)
			count++
		}
	}
	if count == 0 {
		return b.sampleFill(box)
	}
	return fmt.Sprintf("#%02x%02x%02x", r/count, g/count, bl/count)
}

func averageLuma(img image.Image, outer geometry.Rect, excluded geometry.Rect) float64 {
	stepX := maxInt(1, outer.Width/10)
	stepY := maxInt(1, outer.Height/10)
	total := 0.0
	count := 0.0
	for y := outer.Y; y < outer.Bottom(); y += stepY {
		for x := outer.X; x < outer.Right(); x += stepX {
			if x >= excluded.X && x < excluded.Right() && y >= excluded.Y && y < excluded.Bottom() {
				continue
			}
			r, g, b, _ := rgba8(img.At(x, y))
			total += 0.2126*float64(r) + 0.7152*float64(g) + 0.0722*float64(b)
			count++
		}
	}
	if count == 0 {
		return 255
	}
	return total / count
}

func decodeSource(path string) image.Image {
	if strings.TrimSpace(path) == "" {
		return nil
	}
	file, err := os.Open(path)
	if err != nil {
		return nil
	}
	defer file.Close()
	img, err := png.Decode(file)
	if err != nil {
		return nil
	}
	return img
}

func rgba8(c color.Color) (uint32, uint32, uint32, uint32) {
	r, g, b, a := c.RGBA()
	return r >> 8, g >> 8, b >> 8, a >> 8
}

func quantize(value uint32) uint32 {
	return value / 16 * 16
}

func textEvidence(items []contract.Evidence) []contract.Evidence {
	out := make([]contract.Evidence, 0)
	for _, item := range items {
		if canonicalRole(item.RoleHint) == "text" && strings.TrimSpace(item.Meta["text"]) != "" {
			out = append(out, item)
		}
	}
	return out
}

func sortedEvidence(items []contract.Evidence) []contract.Evidence {
	out := append([]contract.Evidence(nil), items...)
	sort.SliceStable(out, func(i, j int) bool {
		ri, rj := materializePriority(out[i]), materializePriority(out[j])
		if ri != rj {
			return ri < rj
		}
		a, b := out[i].BBox, out[j].BBox
		if a.Y != b.Y {
			return a.Y < b.Y
		}
		if a.X != b.X {
			return a.X < b.X
		}
		return out[i].ID < out[j].ID
	})
	return out
}

func materializePriority(item contract.Evidence) int {
	switch canonicalRole(item.RoleHint) {
	case "texture_fragment", "unknown":
		return 1
	case "shape", "line":
		return 2
	case "image":
		return 3
	case "icon":
		return 4
	case "text":
		return 5
	default:
		return 6
	}
}

func canonicalRole(value string) string {
	role := strings.ToLower(strings.TrimSpace(value))
	switch role {
	case "textview":
		return "text"
	case "imageview":
		return "image"
	case "background":
		return "shape"
	case "shape", "line", "image", "icon", "text", "texture_fragment", "unknown":
		return role
	default:
		return role
	}
}

func sourceRefs(item contract.Evidence, role string) []contract.SourceRef {
	refs := []contract.SourceRef{{
		Kind: "layout_evidence",
		ID:   item.ID,
		Role: role,
	}}
	refs = append(refs, item.SourceRefs...)
	return refs
}

func compactMedia(box geometry.Rect, bounds geometry.Rect) bool {
	if box.Empty() || bounds.Empty() {
		return false
	}
	areaRatio := ratio(box.Area(), bounds.Area())
	if areaRatio <= 0.08 {
		return true
	}
	return box.Width <= bounds.Width*45/100 && box.Height <= bounds.Height*28/100
}

func structuralBand(box geometry.Rect, bounds geometry.Rect) bool {
	if box.Empty() || bounds.Empty() {
		return false
	}
	return box.Width >= bounds.Width*85/100 && box.Height <= bounds.Height*16/100
}

func microFragment(box geometry.Rect, bounds geometry.Rect) bool {
	limit := maxInt(32, bounds.Area()/300000)
	return box.Area() < limit || box.Width <= 2 || box.Height <= 2
}

func fullPageBacking(bounds geometry.Rect, box geometry.Rect) bool {
	if bounds.Empty() || box.Empty() {
		return false
	}
	if geometry.IoA(bounds, box) >= 0.95 {
		return true
	}
	return ratio(box.Area(), bounds.Area()) >= 0.92
}

func centerInside(container geometry.Rect, child geometry.Rect) bool {
	if container.Empty() || child.Empty() {
		return false
	}
	cx := child.X + child.Width/2
	cy := child.Y + child.Height/2
	return cx >= container.X && cx <= container.Right() && cy >= container.Y && cy <= container.Bottom()
}

func expand(box geometry.Rect, by int) geometry.Rect {
	return geometry.Rect{
		X:      box.X - by,
		Y:      box.Y - by,
		Width:  box.Width + by*2,
		Height: box.Height + by*2,
	}
}

func ratio(a int, b int) float64 {
	if a <= 0 || b <= 0 {
		return 0
	}
	return float64(a) / float64(b)
}

func maxInt(a int, b int) int {
	if a > b {
		return a
	}
	return b
}

func minInt(a int, b int) int {
	if a < b {
		return a
	}
	return b
}
