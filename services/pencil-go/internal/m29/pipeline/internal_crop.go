package pipeline

import (
	"image"
	"math"
	"sort"

	"github.com/luqing-studio/image-figma/services/pencil-go/internal/m29/contract"
	"github.com/luqing-studio/image-figma/services/pencil-go/internal/m29/primitive"
)

type rasterCropCandidate struct {
	BBox    contract.BBox
	Parent  contract.BBox
	Reasons []string
}

func detectInternalRasterCropCandidates(img image.Image, primitives []contract.Primitive) []rasterCropCandidate {
	bounds := img.Bounds()
	imageWidth, imageHeight := bounds.Dx(), bounds.Dy()
	imageArea := imageWidth * imageHeight
	if imageArea <= 0 {
		return nil
	}

	var candidates []rasterCropCandidate
	for _, p := range primitives {
		if p.PrimitiveType != "image_region" {
			continue
		}
		if !largeRasterParent(p.BBox, imageWidth, imageHeight) {
			continue
		}
		candidates = append(candidates, repeatedRasterSlots(img, p.BBox)...)
	}
	candidates = filterRepeatedRasterCandidates(candidates)
	candidates = normalizeRepeatedRasterSlotHeights(candidates)
	candidates = removeExistingRasterDuplicates(candidates, primitives)
	candidates = filterRepeatedRasterCandidates(candidates)
	return candidates
}

func largeRasterParent(box contract.BBox, imageWidth int, imageHeight int) bool {
	if box.Width <= 0 || box.Height <= 0 {
		return false
	}
	imageArea := max(1, imageWidth*imageHeight)
	if area(box) < imageArea/10 {
		return false
	}
	if box.Width < imageWidth/3 || box.Height < imageHeight/5 {
		return false
	}
	return true
}

func repeatedRasterSlots(img image.Image, parent contract.BBox) []rasterCropCandidate {
	edge := rasterEdgeMap(img, parent)
	if len(edge) == 0 || len(edge[0]) == 0 {
		return nil
	}
	rowProjection := rowEdgeProjection(edge)
	rowProjection = smoothProjection(rowProjection, 9)
	rowThreshold := maxFloat64(0.025, percentileFloat(rowProjection, 0.50)*0.75)
	rowBands := projectionSegments(rowProjection, rowThreshold, max(24, parent.Height/32))
	rowBands = mergeCloseSegments(rowBands, max(6, parent.Height/110))

	var slots []rasterCropCandidate
	for _, band := range rowBands {
		rowHeight := band.End - band.Start
		if rowHeight <= 0 {
			continue
		}
		colProjection := colEdgeProjection(edge, band.Start, band.End)
		colProjection = smoothProjection(colProjection, 7)
		colThreshold := maxFloat64(0.025, percentileFloat(colProjection, 0.50)*0.75)
		colBands := projectionSegments(colProjection, colThreshold, max(8, parent.Width/100))
		colBands = mergeCloseSegments(colBands, max(4, parent.Width/160))
		for _, col := range colBands {
			box := contract.BBox{
				X:      parent.X + col.Start,
				Y:      parent.Y + band.Start,
				Width:  col.End - col.Start,
				Height: rowHeight,
			}
			box = fitInternalRasterSlot(box, parent)
			sideRail := sideRailSlot(box, parent)
			if !validInternalRasterSlot(img, box, parent, sideRail) {
				continue
			}
			reasons := []string{"internal_raster_crop_candidate", "repeated_internal_raster_slot"}
			if sideRail {
				reasons = append(reasons, "side_rail_crop_candidate")
			}
			slots = append(slots, rasterCropCandidate{BBox: box, Parent: parent, Reasons: reasons})
		}
	}
	if hero, ok := heroRasterCropCandidate(img, parent, slots); ok {
		slots = append(slots, hero)
	}
	return slots
}

func heroRasterCropCandidate(img image.Image, parent contract.BBox, slots []rasterCropCandidate) (rasterCropCandidate, bool) {
	if len(slots) < 4 {
		return rasterCropCandidate{}, false
	}
	rowGroups := groupRasterSlotsByRow(slots)
	if len(rowGroups) < 2 {
		return rasterCropCandidate{}, false
	}
	firstRow := rowGroups[0]
	firstTop := slots[firstRow[0]].BBox.Y
	firstBottom := 0
	for _, idx := range firstRow {
		firstBottom = max(firstBottom, bottomBox(slots[idx].BBox))
	}
	if firstTop-parent.Y < max(40, parent.Height/8) {
		return rasterCropCandidate{}, false
	}
	bottomPad := max(6, min(14, parent.Height/120))
	xPad := max(2, min(4, parent.Width/150))
	box := clampBBox(contract.BBox{
		X:      parent.X + xPad,
		Y:      parent.Y,
		Width:  parent.Width - xPad*2,
		Height: firstBottom - parent.Y + bottomPad,
	}, parent)
	if box.Height < parent.Height/5 || box.Height > parent.Height*2/3 {
		return rasterCropCandidate{}, false
	}
	measurements := primitive.MeasureSurface(img, box, primitive.RGB{})
	if measurements.EdgeDensity < 0.08 || measurements.ColorCount < 80 || measurements.TextureScore < 0.35 {
		return rasterCropCandidate{}, false
	}
	return rasterCropCandidate{
		BBox:   box,
		Parent: parent,
		Reasons: []string{
			"internal_raster_crop_candidate",
			"hero_raster_crop_candidate",
			"repeated_internal_raster_slot_context",
		},
	}, true
}

func fitInternalRasterSlot(box contract.BBox, parent contract.BBox) contract.BBox {
	horizontalPad := max(2, min(8, box.Width/18))
	verticalPad := max(6, min(18, box.Height/8))
	return clampBBox(contract.BBox{
		X:      box.X - horizontalPad,
		Y:      box.Y - verticalPad,
		Width:  box.Width + horizontalPad*2,
		Height: box.Height + verticalPad*2,
	}, parent)
}

func clampBBox(box contract.BBox, bounds contract.BBox) contract.BBox {
	x1 := max(bounds.X, box.X)
	y1 := max(bounds.Y, box.Y)
	x2 := min(bounds.X+bounds.Width, box.X+box.Width)
	y2 := min(bounds.Y+bounds.Height, box.Y+box.Height)
	return contract.BBox{X: x1, Y: y1, Width: max(0, x2-x1), Height: max(0, y2-y1)}
}

type projectionSegment struct {
	Start int
	End   int
}

func rasterEdgeMap(img image.Image, box contract.BBox) [][]bool {
	bounds := img.Bounds()
	x1 := max(bounds.Min.X, box.X)
	y1 := max(bounds.Min.Y, box.Y)
	x2 := min(bounds.Max.X, box.X+box.Width)
	y2 := min(bounds.Max.Y, box.Y+box.Height)
	if x2-x1 <= 2 || y2-y1 <= 2 {
		return nil
	}
	width := x2 - x1
	height := y2 - y1
	edge := make([][]bool, height)
	for y := range edge {
		edge[y] = make([]bool, width)
	}
	for y := y1 + 1; y < y2-1; y++ {
		for x := x1 + 1; x < x2-1; x++ {
			gx := math.Abs(grayAt(img, x+1, y) - grayAt(img, x-1, y))
			gy := math.Abs(grayAt(img, x, y+1) - grayAt(img, x, y-1))
			edge[y-y1][x-x1] = gx+gy > 48
		}
	}
	return edge
}

func rowEdgeProjection(edge [][]bool) []float64 {
	out := make([]float64, len(edge))
	for y, row := range edge {
		count := 0
		for _, v := range row {
			if v {
				count++
			}
		}
		out[y] = float64(count) / float64(max(1, len(row)))
	}
	return out
}

func colEdgeProjection(edge [][]bool, y1 int, y2 int) []float64 {
	if len(edge) == 0 || len(edge[0]) == 0 {
		return nil
	}
	y1 = max(0, y1)
	y2 = min(len(edge), y2)
	if y2 <= y1 {
		return nil
	}
	width := len(edge[0])
	out := make([]float64, width)
	for x := 0; x < width; x++ {
		count := 0
		for y := y1; y < y2; y++ {
			if edge[y][x] {
				count++
			}
		}
		out[x] = float64(count) / float64(y2-y1)
	}
	return out
}

func smoothProjection(values []float64, window int) []float64 {
	if len(values) == 0 || window <= 1 {
		return append([]float64(nil), values...)
	}
	out := make([]float64, len(values))
	half := window / 2
	for i := range values {
		start := max(0, i-half)
		end := min(len(values), i+half+1)
		sum := 0.0
		for _, v := range values[start:end] {
			sum += v
		}
		out[i] = sum / float64(end-start)
	}
	return out
}

func projectionSegments(values []float64, threshold float64, minLen int) []projectionSegment {
	var out []projectionSegment
	inSegment := false
	start := 0
	for i, v := range values {
		if v > threshold && !inSegment {
			start = i
			inSegment = true
		}
		if (v <= threshold || i == len(values)-1) && inSegment {
			end := i
			if v > threshold && i == len(values)-1 {
				end = i + 1
			}
			if end-start >= minLen {
				out = append(out, projectionSegment{Start: start, End: end})
			}
			inSegment = false
		}
	}
	return out
}

func mergeCloseSegments(segments []projectionSegment, maxGap int) []projectionSegment {
	if len(segments) <= 1 {
		return segments
	}
	out := []projectionSegment{segments[0]}
	for _, segment := range segments[1:] {
		last := &out[len(out)-1]
		if segment.Start-last.End <= maxGap {
			last.End = max(last.End, segment.End)
			continue
		}
		out = append(out, segment)
	}
	return out
}

func validInternalRasterSlot(img image.Image, box contract.BBox, parent contract.BBox, sideRail bool) bool {
	if box.Width < 18 || box.Height < 32 || area(box) < 900 {
		return false
	}
	if box.Width > parent.Width*3/4 && box.Height > parent.Height/3 {
		return false
	}
	if box.Width < parent.Width/30 && box.Height < parent.Height/12 {
		return false
	}
	measurements := primitive.MeasureSurface(img, box, primitive.RGB{})
	if measurements.EdgeDensity < 0.24 || measurements.ColorCount < 120 || measurements.TextureScore < 0.58 {
		return false
	}
	if sideRail {
		return true
	}
	return box.X+box.Width/2 <= parent.X+parent.Width*3/10
}

func sideRailSlot(box contract.BBox, parent contract.BBox) bool {
	centerX := box.X + box.Width/2
	return centerX >= parent.X+parent.Width*7/8 &&
		box.Width <= parent.Width/5 &&
		box.Height >= box.Width
}

func filterRepeatedRasterCandidates(candidates []rasterCropCandidate) []rasterCropCandidate {
	if len(candidates) == 0 {
		return nil
	}
	groups := groupRasterSlotsByColumn(candidates)
	keep := map[int]bool{}
	for i, candidate := range candidates {
		if candidateHasReason(candidate, "hero_raster_crop_candidate") {
			keep[i] = true
		}
	}
	for _, group := range groups {
		if len(group) < 2 {
			continue
		}
		sort.SliceStable(group, func(i, j int) bool {
			return candidates[group[i]].BBox.Y < candidates[group[j]].BBox.Y
		})
		distinctRows := 1
		lastY := candidates[group[0]].BBox.Y
		for _, idx := range group[1:] {
			if abs(candidates[idx].BBox.Y-lastY) >= min(candidates[idx].BBox.Height, candidates[group[0]].BBox.Height)/2 {
				distinctRows++
				lastY = candidates[idx].BBox.Y
			}
		}
		if distinctRows < 2 {
			continue
		}
		for _, idx := range group {
			keep[idx] = true
		}
	}
	var out []rasterCropCandidate
	for i, candidate := range candidates {
		if !keep[i] {
			continue
		}
		if duplicateRasterCandidate(candidate.BBox, out) {
			continue
		}
		out = append(out, candidate)
	}
	return out
}

func groupRasterSlotsByRow(candidates []rasterCropCandidate) [][]int {
	indexes := make([]int, 0, len(candidates))
	for i, candidate := range candidates {
		if candidateHasReason(candidate, "hero_raster_crop_candidate") {
			continue
		}
		indexes = append(indexes, i)
	}
	sort.SliceStable(indexes, func(i, j int) bool {
		a, b := candidates[indexes[i]].BBox, candidates[indexes[j]].BBox
		if abs(a.Y-b.Y) > max(8, min(a.Height, b.Height)/5) {
			return a.Y < b.Y
		}
		return a.X < b.X
	})
	var groups [][]int
	for _, idx := range indexes {
		placed := false
		for gi := range groups {
			reference := candidates[groups[gi][0]].BBox
			if similarRasterRow(reference, candidates[idx].BBox) {
				groups[gi] = append(groups[gi], idx)
				placed = true
				break
			}
		}
		if !placed {
			groups = append(groups, []int{idx})
		}
	}
	return groups
}

func groupRasterSlotsByColumn(candidates []rasterCropCandidate) [][]int {
	var groups [][]int
	for i, candidate := range candidates {
		placed := false
		for gi := range groups {
			reference := candidates[groups[gi][0]].BBox
			if similarRasterColumn(reference, candidate.BBox) {
				groups[gi] = append(groups[gi], i)
				placed = true
				break
			}
		}
		if !placed {
			groups = append(groups, []int{i})
		}
	}
	return groups
}

func normalizeRepeatedRasterSlotHeights(candidates []rasterCropCandidate) []rasterCropCandidate {
	out := append([]rasterCropCandidate(nil), candidates...)
	for _, group := range groupRasterSlotsByColumn(out) {
		if len(group) < 2 {
			continue
		}
		heights := make([]int, 0, len(group))
		for _, idx := range group {
			heights = append(heights, out[idx].BBox.Height)
		}
		sort.Ints(heights)
		targetHeight := heights[len(heights)/2]
		if targetHeight <= 0 {
			continue
		}
		for _, idx := range group {
			if out[idx].BBox.Height*5 >= targetHeight*4 {
				continue
			}
			box := out[idx].BBox
			box.Height = targetHeight
			if out[idx].Parent.Width > 0 && out[idx].Parent.Height > 0 {
				box = clampBBox(box, out[idx].Parent)
			}
			out[idx].BBox = box
		}
	}
	return out
}

func similarRasterColumn(a contract.BBox, b contract.BBox) bool {
	ac := a.X + a.Width/2
	bc := b.X + b.Width/2
	centerTolerance := max(12, min(a.Width, b.Width)/3)
	if abs(ac-bc) > centerTolerance {
		return false
	}
	widthRatio := float64(abs(a.Width-b.Width)) / float64(max(1, max(a.Width, b.Width)))
	return widthRatio <= 0.35
}

func similarRasterRow(a contract.BBox, b contract.BBox) bool {
	ac := a.Y + a.Height/2
	bc := b.Y + b.Height/2
	centerTolerance := max(12, min(a.Height, b.Height)/3)
	if abs(ac-bc) > centerTolerance {
		return false
	}
	heightRatio := float64(abs(a.Height-b.Height)) / float64(max(1, max(a.Height, b.Height)))
	return heightRatio <= 0.35
}

func removeExistingRasterDuplicates(candidates []rasterCropCandidate, primitives []contract.Primitive) []rasterCropCandidate {
	var out []rasterCropCandidate
	for _, candidate := range candidates {
		if similarExistingRaster(candidate.BBox, primitives) {
			continue
		}
		if duplicateRasterCandidate(candidate.BBox, out) {
			continue
		}
		out = append(out, candidate)
	}
	return out
}

func similarExistingRaster(box contract.BBox, primitives []contract.Primitive) bool {
	for _, p := range primitives {
		if p.PrimitiveType != "image_region" {
			continue
		}
		pArea := area(p.BBox)
		boxArea := area(box)
		if pArea > boxArea*4 || boxArea > pArea*4 {
			continue
		}
		if iouBBox(p.BBox, box) >= 0.70 {
			return true
		}
	}
	return false
}

func duplicateRasterCandidate(box contract.BBox, existing []rasterCropCandidate) bool {
	for _, item := range existing {
		if iouBBox(item.BBox, box) >= 0.80 {
			return true
		}
	}
	return false
}

func candidateHasReason(candidate rasterCropCandidate, reason string) bool {
	for _, item := range candidate.Reasons {
		if item == reason {
			return true
		}
	}
	return false
}

func bottomBox(box contract.BBox) int {
	return box.Y + box.Height
}

func iouBBox(a contract.BBox, b contract.BBox) float64 {
	x1 := max(a.X, b.X)
	y1 := max(a.Y, b.Y)
	x2 := min(a.X+a.Width, b.X+b.Width)
	y2 := min(a.Y+a.Height, b.Y+b.Height)
	intersection := area(contract.BBox{X: x1, Y: y1, Width: x2 - x1, Height: y2 - y1})
	if intersection <= 0 {
		return 0
	}
	union := area(a) + area(b) - intersection
	if union <= 0 {
		return 0
	}
	return float64(intersection) / float64(union)
}

func percentileFloat(values []float64, p float64) float64 {
	if len(values) == 0 {
		return 0
	}
	sorted := append([]float64(nil), values...)
	sort.Float64s(sorted)
	idx := int(math.Round(float64(len(sorted)-1) * p))
	idx = max(0, min(len(sorted)-1, idx))
	return sorted[idx]
}

func grayAt(img image.Image, x int, y int) float64 {
	c := primitive.RGBAt(img, x, y)
	return 0.299*float64(c.R) + 0.587*float64(c.G) + 0.114*float64(c.B)
}

func maxFloat64(a float64, b float64) float64 {
	if a > b {
		return a
	}
	return b
}
