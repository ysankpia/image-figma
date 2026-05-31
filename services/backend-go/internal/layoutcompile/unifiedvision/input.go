package unifiedvision

import (
	"encoding/json"
	"fmt"
	"sort"
	"strings"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/image/geometry"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/layoutir/contract"
)

func BuildInput(doc contract.Document, options Options) Input {
	options = options.withDefaults()
	bounds := geometry.Rect{Width: doc.SourceImage.Width, Height: doc.SourceImage.Height}
	input := Input{
		Version:     InputVersion,
		GeneratedAt: timestamp(),
		SourceImage: doc.SourceImage,
		Provider:    options.providerMeta(),
		Instructions: Instructions{
			Task: "Infer layout relationships for existing UI evidence inside each cropped section.",
			Must: []string{
				"Return strict JSON only.",
				"Reference only evidence IDs provided in the batch.",
				"Keep OCR text unchanged; text is reference context only.",
				"Use bbox values only to understand geometry; do not output new bboxes.",
				"Prefer small credible flat groups with 2 to 6 items.",
			},
			MustNot: []string{
				"Do not output HTML, CSS, SVG, Figma nodes, or prose.",
				"Do not invent evidence IDs, OCR text, coordinates, assets, colors, or page content.",
				"Do not put the same evidence ID in more than one group in the same response.",
				"Do not create nested groups in v1; this contract is flat.",
			},
			OutputShape: `{"version":"unified_vision_result.v1","groups":[{"id":"group_1","name":"short_name","direction":"horizontal","gap":12,"members":["evidence_id_1","evidence_id_2"],"confidence":0.8,"reason":"short reason"}],"elementStyles":{"evidence_id_1":{"fontSize":16,"fontWeight":600,"color":"#111111"}},"ungrouped":[],"warnings":[]}`,
		},
	}
	for _, section := range sections(doc.Root) {
		items := flowEvidenceForSection(doc.Evidence, section)
		if len(items) < 2 {
			continue
		}
		input.Batches = append(input.Batches, splitSection(section, items, bounds, options)...)
	}
	for i := range input.Batches {
		input.Batches[i].ID = fmt.Sprintf("uv_batch_%04d", i+1)
		for j := range input.Batches[i].Evidence {
			input.Batches[i].Evidence[j].BBoxLocal = localBBox(input.Batches[i].Evidence[j].BBox, input.Batches[i].CropBBox)
		}
	}
	return input
}

func sections(root contract.Node) []contract.Node {
	var out []contract.Node
	for _, child := range root.Children {
		if child.Type == contract.NodeSection {
			out = append(out, child)
		}
	}
	sort.SliceStable(out, func(i, j int) bool {
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

func flowEvidenceForSection(evidence []contract.Evidence, section contract.Node) []EvidenceItem {
	allowed := map[string]bool{}
	for _, ref := range section.SourceRefs {
		if ref.Kind == "layout_evidence" && ref.ID != "" {
			allowed[ref.ID] = true
		}
	}
	out := make([]EvidenceItem, 0)
	for _, item := range evidence {
		if !flowRole(item.RoleHint) {
			continue
		}
		if len(allowed) > 0 {
			if !allowed[item.ID] {
				continue
			}
		} else if !centerInside(section.BBox, item.BBox) && geometry.IoA(item.BBox, section.BBox) < 0.50 {
			continue
		}
		out = append(out, EvidenceItem{
			ID:         item.ID,
			Kind:       item.Kind,
			RoleHint:   item.RoleHint,
			BBox:       item.BBox,
			Text:       strings.TrimSpace(item.Meta["text"]),
			Source:     item.Source,
			Confidence: item.Confidence,
			SourceRefs: append([]contract.SourceRef(nil), item.SourceRefs...),
		})
	}
	sortEvidence(out)
	return out
}

func splitSection(section contract.Node, items []EvidenceItem, bounds geometry.Rect, options Options) []BatchInput {
	crop := clamp(expand(section.BBox, options.CropPadding), bounds)
	if crop.Empty() {
		crop = section.BBox
	}
	return splitRecursive(section.ID, section.BBox, crop, items, bounds, options, 0)
}

func splitRecursive(sectionID string, sectionBox geometry.Rect, cropBox geometry.Rect, items []EvidenceItem, bounds geometry.Rect, options Options, depth int) []BatchInput {
	sortEvidence(items)
	complexity := computeComplexity(items, cropBox)
	if acceptableBatch(complexity, options) || len(items) < 3 || depth >= 8 {
		return []BatchInput{newBatch(sectionID, sectionBox, cropBox, complexity, items)}
	}
	left, right, leftBox, rightBox := splitByWhitespace(items, cropBox)
	if len(left) == 0 || len(right) == 0 {
		left, right, leftBox, rightBox = splitByYBands(items, cropBox)
	}
	if len(left) == 0 || len(right) == 0 {
		left, right, leftBox, rightBox = splitByMedianY(items, cropBox)
	}
	if len(left) == 0 || len(right) == 0 {
		return hardChunks(sectionID, sectionBox, cropBox, items, options)
	}
	var out []BatchInput
	out = append(out, splitRecursive(sectionID, sectionBox, clamp(expand(leftBox, options.CropPadding), bounds), left, bounds, options, depth+1)...)
	out = append(out, splitRecursive(sectionID, sectionBox, clamp(expand(rightBox, options.CropPadding), bounds), right, bounds, options, depth+1)...)
	return out
}

func acceptableBatch(complexity Complexity, options Options) bool {
	return complexity.ItemCount <= options.MaxItemsPerBatch &&
		complexity.ItemCount <= options.HardMaxItemsPerBatch &&
		complexity.Score <= options.MaxComplexity
}

func newBatch(sectionID string, sectionBox geometry.Rect, cropBox geometry.Rect, complexity Complexity, items []EvidenceItem) BatchInput {
	copied := append([]EvidenceItem(nil), items...)
	sortEvidence(copied)
	return BatchInput{
		SectionID:   sectionID,
		SectionBBox: sectionBox,
		CropBBox:    cropBox,
		Complexity:  complexity,
		Evidence:    copied,
		SourceRefs:  sourceRefs(evidenceIDs(copied), "unified_vision_batch_member"),
	}
}

func hardChunks(sectionID string, sectionBox geometry.Rect, cropBox geometry.Rect, items []EvidenceItem, options Options) []BatchInput {
	size := maxInt(2, minInt(options.MaxItemsPerBatch, options.HardMaxItemsPerBatch))
	var out []BatchInput
	for i := 0; i < len(items); i += size {
		end := minInt(len(items), i+size)
		chunk := append([]EvidenceItem(nil), items[i:end]...)
		box := unionEvidence(chunk)
		out = append(out, newBatch(sectionID, sectionBox, clamp(expand(box, options.CropPadding), cropBox), computeComplexity(chunk, box), chunk))
	}
	return out
}

func evidenceIDs(items []EvidenceItem) []string {
	out := make([]string, 0, len(items))
	for _, item := range items {
		out = append(out, item.ID)
	}
	sort.Strings(out)
	return out
}

func splitByWhitespace(items []EvidenceItem, cropBox geometry.Rect) ([]EvidenceItem, []EvidenceItem, geometry.Rect, geometry.Rect) {
	if len(items) < 4 {
		return nil, nil, geometry.Rect{}, geometry.Rect{}
	}
	sorted := append([]EvidenceItem(nil), items...)
	sortEvidence(sorted)
	heights := make([]int, 0, len(sorted))
	for _, item := range sorted {
		if item.BBox.Height > 0 {
			heights = append(heights, item.BBox.Height)
		}
	}
	unit := median(heights)
	if unit <= 0 {
		unit = 12
	}
	threshold := maxInt(16, unit*2)
	bestIndex := -1
	bestGap := 0
	currentBottom := sorted[0].BBox.Bottom()
	for i := 1; i < len(sorted); i++ {
		gap := sorted[i].BBox.Y - currentBottom
		if gap > bestGap && gap >= threshold && i >= 2 && len(sorted)-i >= 2 {
			bestGap = gap
			bestIndex = i
		}
		if sorted[i].BBox.Bottom() > currentBottom {
			currentBottom = sorted[i].BBox.Bottom()
		}
	}
	if bestIndex < 0 {
		return nil, nil, geometry.Rect{}, geometry.Rect{}
	}
	top := append([]EvidenceItem(nil), sorted[:bestIndex]...)
	bottom := append([]EvidenceItem(nil), sorted[bestIndex:]...)
	return top, bottom, unionEvidence(top).Intersect(cropBox), unionEvidence(bottom).Intersect(cropBox)
}

func splitByYBands(items []EvidenceItem, cropBox geometry.Rect) ([]EvidenceItem, []EvidenceItem, geometry.Rect, geometry.Rect) {
	bands := yBands(items)
	if len(bands) < 2 {
		return nil, nil, geometry.Rect{}, geometry.Rect{}
	}
	cut := len(bands) / 2
	var top, bottom []EvidenceItem
	for i, band := range bands {
		if i < cut {
			top = append(top, band...)
		} else {
			bottom = append(bottom, band...)
		}
	}
	if len(top) < 2 || len(bottom) < 2 {
		return nil, nil, geometry.Rect{}, geometry.Rect{}
	}
	return top, bottom, unionEvidence(top).Intersect(cropBox), unionEvidence(bottom).Intersect(cropBox)
}

func splitByMedianY(items []EvidenceItem, cropBox geometry.Rect) ([]EvidenceItem, []EvidenceItem, geometry.Rect, geometry.Rect) {
	if len(items) < 4 {
		return nil, nil, geometry.Rect{}, geometry.Rect{}
	}
	sorted := append([]EvidenceItem(nil), items...)
	sort.SliceStable(sorted, func(i, j int) bool {
		ay := sorted[i].BBox.Y + sorted[i].BBox.Height/2
		by := sorted[j].BBox.Y + sorted[j].BBox.Height/2
		if ay != by {
			return ay < by
		}
		return sorted[i].ID < sorted[j].ID
	})
	mid := len(sorted) / 2
	top := append([]EvidenceItem(nil), sorted[:mid]...)
	bottom := append([]EvidenceItem(nil), sorted[mid:]...)
	if len(top) == 0 || len(bottom) == 0 {
		return nil, nil, geometry.Rect{}, geometry.Rect{}
	}
	return top, bottom, unionEvidence(top).Intersect(cropBox), unionEvidence(bottom).Intersect(cropBox)
}

func computeComplexity(items []EvidenceItem, box geometry.Rect) Complexity {
	out := Complexity{ItemCount: len(items)}
	if len(items) == 0 {
		return out
	}
	totalArea := 0
	roles := map[string]bool{}
	var union geometry.Rect
	for _, item := range items {
		totalArea += item.BBox.Area()
		roles[strings.ToLower(strings.TrimSpace(item.RoleHint))] = true
		union = union.Union(item.BBox)
	}
	if box.Area() > 0 {
		out.Density = float64(totalArea) / float64(box.Area())
	}
	out.RoleMixCount = len(roles)
	out.YBandCount = len(yBands(items))
	out.VerticalSpan = union.Height
	out.OverlapPairs, out.ContainmentPairs = overlapStats(items)
	gaps := horizontalGaps(items)
	out.GapVariance = variance(gaps)
	unit := medianHeights(items)
	for _, gap := range gaps {
		if gap > maxInt(48, unit*3) {
			out.LargeGapCount++
		}
	}
	out.NeighborDensity = neighborDensity(items)
	out.Score = float64(out.ItemCount)*2.0 +
		float64(out.YBandCount)*8.0 +
		float64(out.RoleMixCount)*4.0 +
		float64(out.OverlapPairs)*2.5 +
		float64(out.ContainmentPairs)*4.0 +
		float64(out.LargeGapCount)*5.0 +
		float64(out.GapVariance)/300.0 +
		out.Density*35.0 +
		out.NeighborDensity*20.0
	return out
}

func yBands(items []EvidenceItem) [][]EvidenceItem {
	if len(items) == 0 {
		return nil
	}
	sorted := append([]EvidenceItem(nil), items...)
	sortEvidence(sorted)
	var bands [][]EvidenceItem
	current := []EvidenceItem{sorted[0]}
	currentBottom := sorted[0].BBox.Bottom()
	for _, item := range sorted[1:] {
		centerY := item.BBox.Y + item.BBox.Height/2
		if centerY > currentBottom {
			bands = append(bands, current)
			current = []EvidenceItem{item}
			currentBottom = item.BBox.Bottom()
			continue
		}
		current = append(current, item)
		if item.BBox.Bottom() > currentBottom {
			currentBottom = item.BBox.Bottom()
		}
	}
	bands = append(bands, current)
	return bands
}

func horizontalGaps(items []EvidenceItem) []int {
	bands := yBands(items)
	var gaps []int
	for _, band := range bands {
		sort.SliceStable(band, func(i, j int) bool {
			if band[i].BBox.X != band[j].BBox.X {
				return band[i].BBox.X < band[j].BBox.X
			}
			return band[i].ID < band[j].ID
		})
		for i := 1; i < len(band); i++ {
			gap := band[i].BBox.X - band[i-1].BBox.Right()
			if gap > 0 {
				gaps = append(gaps, gap)
			}
		}
	}
	return gaps
}

func medianHeights(items []EvidenceItem) int {
	heights := make([]int, 0, len(items))
	for _, item := range items {
		if item.BBox.Height > 0 {
			heights = append(heights, item.BBox.Height)
		}
	}
	return median(heights)
}

func overlapStats(items []EvidenceItem) (int, int) {
	overlaps := 0
	contains := 0
	for i := 0; i < len(items); i++ {
		for j := i + 1; j < len(items); j++ {
			a, b := items[i].BBox, items[j].BBox
			if a.Intersect(b).Area() > 0 {
				overlaps++
			}
			if geometry.IoA(a, b) >= 0.90 || geometry.IoA(b, a) >= 0.90 {
				contains++
			}
		}
	}
	return overlaps, contains
}

func neighborDensity(items []EvidenceItem) float64 {
	if len(items) <= 1 {
		return 0
	}
	unit := maxInt(12, medianHeights(items)*2)
	near := 0
	for i := 0; i < len(items); i++ {
		for j := i + 1; j < len(items); j++ {
			if manhattanCenter(items[i].BBox, items[j].BBox) <= unit*3 {
				near++
			}
		}
	}
	return float64(near) / float64(len(items))
}

func manhattanCenter(a geometry.Rect, b geometry.Rect) int {
	ax, ay := a.X+a.Width/2, a.Y+a.Height/2
	bx, by := b.X+b.Width/2, b.Y+b.Height/2
	dx := ax - bx
	if dx < 0 {
		dx = -dx
	}
	dy := ay - by
	if dy < 0 {
		dy = -dy
	}
	return dx + dy
}

func promptEvidenceJSON(batch BatchInput) string {
	type promptItem struct {
		ID        string        `json:"id"`
		Role      string        `json:"role"`
		BBox      geometry.Rect `json:"bbox"`
		BBoxLocal geometry.Rect `json:"bboxLocal"`
		Text      string        `json:"text,omitempty"`
	}
	items := make([]promptItem, 0, len(batch.Evidence))
	for _, item := range batch.Evidence {
		items = append(items, promptItem{
			ID:        item.ID,
			Role:      item.RoleHint,
			BBox:      item.BBox,
			BBoxLocal: item.BBoxLocal,
			Text:      item.Text,
		})
	}
	data, _ := json.MarshalIndent(items, "", "  ")
	return string(data)
}
