package pipeline

import (
	"image"
	"sort"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/components"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/contract"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/mask"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/ocr"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/primitive"
)

type surfaceCandidate struct {
	BBox            contract.BBox
	Reasons         []string
	BackgroundColor primitive.RGB
}

type surfaceSeed struct {
	X     int
	Y     int
	Color primitive.RGB
}

func detectSurfaceCandidates(img image.Image, blocks []ocr.Block, textMask mask.Mask) []surfaceCandidate {
	bounds := img.Bounds()
	width, height := bounds.Dx(), bounds.Dy()
	var candidates []surfaceCandidate
	for _, block := range blocks {
		seeds := surfaceSeedsForBlock(img, block.BBox, textMask)
		if len(seeds) == 0 {
			continue
		}
		box := growSurfaceFromSeeds(img, seeds, textMask)
		if !validSurfaceCandidate(box, block.BBox, width, height) {
			continue
		}
		candidates = append(candidates, surfaceCandidate{
			BBox:            box,
			Reasons:         []string{"ocr_anchored_low_texture_surface", "local_surface_color_region"},
			BackgroundColor: seeds[0].Color,
		})
	}
	candidates = append(candidates, detectControlSurfaceCandidates(img, blocks, textMask)...)
	return mergeSurfaceCandidates(candidates)
}

func detectControlSurfaceCandidates(img image.Image, blocks []ocr.Block, textMask mask.Mask) []surfaceCandidate {
	bounds := img.Bounds()
	width, height := bounds.Dx(), bounds.Dy()
	var candidates []surfaceCandidate
	for _, block := range blocks {
		search := controlSurfaceSearchBBox(block.BBox, textMask.Width, textMask.Height)
		if candidate, ok := detectControlSurfaceCandidateInSearch(img, block.BBox, search, textMask, []string{"control_surface_candidate", "ocr_anchored_control_surface"}); ok {
			if validControlSurfaceCandidate(candidate.BBox, block.BBox, width, height) && !tightNumericGlyphSurface(block.Text, candidate.BBox, block.BBox) {
				candidates = append(candidates, candidate)
			}
		}
		if !compactControlAnchor(block.BBox, width, height) {
			continue
		}
		wideSearch := horizontalControlSurfaceSearchBBox(block.BBox, width, height)
		if candidate, ok := detectControlSurfaceCandidateInSearch(img, block.BBox, wideSearch, textMask, []string{"control_surface_candidate", "horizontal_control_surface_candidate"}); ok {
			if validControlSurfaceCandidate(candidate.BBox, block.BBox, width, height) && !tightNumericGlyphSurface(block.Text, candidate.BBox, block.BBox) {
				candidates = append(candidates, candidate)
			}
		}
		if candidate, ok := detectContrastControlSurfaceCandidate(img, block.BBox, search, textMask); ok {
			if validControlSurfaceCandidate(candidate.BBox, block.BBox, width, height) && !tightNumericGlyphSurface(block.Text, candidate.BBox, block.BBox) {
				candidates = append(candidates, candidate)
			}
		}
	}
	return candidates
}

func detectControlSurfaceCandidateInSearch(img image.Image, textBox contract.BBox, search contract.BBox, textMask mask.Mask, reasons []string) (surfaceCandidate, bool) {
	seeds := controlSurfaceSeedsForBlock(img, textBox, search, textMask)
	if len(seeds) == 0 {
		return surfaceCandidate{}, false
	}
	box := growControlSurfaceFromSeeds(img, seeds, search, textMask)
	if box.Width >= search.Width-2 || box.Height >= search.Height-2 {
		return surfaceCandidate{}, false
	}
	return surfaceCandidate{
		BBox:            box,
		Reasons:         reasons,
		BackgroundColor: seeds[0].Color,
	}, true
}

func detectSurfaceForegroundComponents(img image.Image, surfaces []surfaceCandidate, textMask mask.Mask) []components.Component {
	bounds := img.Bounds()
	imageWidth, imageHeight := bounds.Dx(), bounds.Dy()
	minArea := max(6, imageWidth*imageHeight/180000)
	var out []components.Component
	for _, surface := range surfaces {
		if surface.BBox.Width <= 0 || surface.BBox.Height <= 0 {
			continue
		}
		localMask := mask.New(imageWidth, imageHeight)
		x1 := max(0, surface.BBox.X)
		y1 := max(0, surface.BBox.Y)
		x2 := min(imageWidth, surface.BBox.X+surface.BBox.Width)
		y2 := min(imageHeight, surface.BBox.Y+surface.BBox.Height)
		for y := y1; y < y2; y++ {
			for x := x1; x < x2; x++ {
				if textMask.Get(x, y) {
					continue
				}
				if primitive.ColorDistance(primitive.RGBAt(img, x, y), surface.BackgroundColor) > 28 {
					localMask.Set(x, y, true)
				}
			}
		}
		for _, comp := range components.ConnectedComponents(localMask, minArea, 0.10) {
			if validSurfaceForegroundComponent(comp, surface.BBox) {
				out = append(out, comp)
			}
		}
	}
	return out
}

func validSurfaceForegroundComponent(comp components.Component, surface contract.BBox) bool {
	if comp.BBox.Width <= 0 || comp.BBox.Height <= 0 {
		return false
	}
	if area(comp.BBox) > area(surface)/3 {
		return false
	}
	if comp.BBox.Width > surface.Width*3/4 && comp.BBox.Height > surface.Height/3 {
		return false
	}
	if comp.BBox.Width <= 2 && comp.BBox.Height <= 2 {
		return false
	}
	return true
}

func surfaceSeedsForBlock(img image.Image, bbox contract.BBox, textMask mask.Mask) []surfaceSeed {
	search := inflateBBox(bbox, max(16, bbox.Width/3), max(10, bbox.Height/2), textMask.Width, textMask.Height)
	type bucket struct {
		Count int
		SumR  int
		SumG  int
		SumB  int
	}
	buckets := map[[3]uint8]*bucket{}
	for y := search.Y; y < search.Y+search.Height; y += 2 {
		for x := search.X; x < search.X+search.Width; x += 2 {
			if textMask.Get(x, y) {
				continue
			}
			if contains(bbox, contract.BBox{X: x, Y: y, Width: 1, Height: 1}, 0) {
				continue
			}
			c := primitive.RGBAt(img, x, y)
			key := [3]uint8{c.R >> 4, c.G >> 4, c.B >> 4}
			b := buckets[key]
			if b == nil {
				b = &bucket{}
				buckets[key] = b
			}
			b.Count++
			b.SumR += int(c.R)
			b.SumG += int(c.G)
			b.SumB += int(c.B)
		}
	}
	if len(buckets) == 0 {
		return nil
	}
	keys := make([][3]uint8, 0, len(buckets))
	for key := range buckets {
		keys = append(keys, key)
	}
	sort.SliceStable(keys, func(i, j int) bool {
		return buckets[keys[i]].Count > buckets[keys[j]].Count
	})
	best := buckets[keys[0]]
	if best.Count < 8 {
		return nil
	}
	target := primitive.RGB{
		R: uint8(best.SumR / best.Count),
		G: uint8(best.SumG / best.Count),
		B: uint8(best.SumB / best.Count),
	}
	var seeds []surfaceSeed
	for y := search.Y; y < search.Y+search.Height; y += 2 {
		for x := search.X; x < search.X+search.Width; x += 2 {
			if textMask.Get(x, y) {
				continue
			}
			if primitive.ColorDistance(primitive.RGBAt(img, x, y), target) <= 34 {
				seeds = append(seeds, surfaceSeed{X: x, Y: y, Color: target})
			}
		}
	}
	return seeds
}

func controlSurfaceSearchBBox(bbox contract.BBox, width int, height int) contract.BBox {
	return inflateBBox(bbox, max(18, bbox.Width/2), max(14, bbox.Height), width, height)
}

func horizontalControlSurfaceSearchBBox(bbox contract.BBox, width int, height int) contract.BBox {
	left := max(24, bbox.Width*2)
	right := max(width*2/3, bbox.Width*8)
	topBottom := max(24, bbox.Height*2)
	x1 := max(0, bbox.X-left)
	y1 := max(0, bbox.Y-topBottom)
	x2 := min(width, bbox.X+bbox.Width+right)
	y2 := min(height, bbox.Y+bbox.Height+topBottom)
	return contract.BBox{X: x1, Y: y1, Width: x2 - x1, Height: y2 - y1}
}

func compactControlAnchor(bbox contract.BBox, imageWidth int, imageHeight int) bool {
	if bbox.Width <= 0 || bbox.Height <= 0 {
		return false
	}
	if bbox.Width > min(96, imageWidth/5) || bbox.Height > 56 {
		return false
	}
	return area(bbox) <= max(1800, imageWidth*imageHeight/420)
}

func controlSurfaceSeedsForBlock(img image.Image, bbox contract.BBox, search contract.BBox, textMask mask.Mask) []surfaceSeed {
	target, ok := dominantControlSurfaceColor(img, bbox, textMask)
	if !ok {
		return nil
	}
	centerX := bbox.X + bbox.Width/2
	centerY := bbox.Y + bbox.Height/2
	var seeds []surfaceSeed
	for y := bbox.Y; y < bbox.Y+bbox.Height; y += 2 {
		for x := bbox.X; x < bbox.X+bbox.Width; x += 2 {
			if !textMask.InBounds(x, y) {
				continue
			}
			if primitive.ColorDistance(primitive.RGBAt(img, x, y), target) <= 12 {
				seeds = append(seeds, surfaceSeed{X: x, Y: y, Color: target})
			}
		}
	}
	if len(seeds) > 0 {
		sort.SliceStable(seeds, func(i, j int) bool {
			di := abs(seeds[i].X-centerX) + abs(seeds[i].Y-centerY)
			dj := abs(seeds[j].X-centerX) + abs(seeds[j].Y-centerY)
			return di < dj
		})
		if len(seeds) > 256 {
			seeds = seeds[:256]
		}
		return seeds
	}
	best := surfaceSeed{}
	bestDistance := -1
	for y := search.Y; y < search.Y+search.Height; y++ {
		for x := search.X; x < search.X+search.Width; x++ {
			if !textMask.InBounds(x, y) {
				continue
			}
			if primitive.ColorDistance(primitive.RGBAt(img, x, y), target) > 12 {
				continue
			}
			distance := abs(x-centerX) + abs(y-centerY)
			if bestDistance == -1 || distance < bestDistance {
				bestDistance = distance
				best = surfaceSeed{X: x, Y: y, Color: target}
			}
		}
	}
	if bestDistance == -1 {
		return nil
	}
	return []surfaceSeed{best}
}

func dominantControlSurfaceColor(img image.Image, textBox contract.BBox, textMask mask.Mask) (primitive.RGB, bool) {
	type bucket struct {
		Count int
		SumR  int
		SumG  int
		SumB  int
	}
	buckets := map[[3]uint8]*bucket{}
	for y := textBox.Y; y < textBox.Y+textBox.Height; y++ {
		for x := textBox.X; x < textBox.X+textBox.Width; x++ {
			if !textMask.InBounds(x, y) {
				continue
			}
			c := primitive.RGBAt(img, x, y)
			key := [3]uint8{c.R >> 3, c.G >> 3, c.B >> 3}
			b := buckets[key]
			if b == nil {
				b = &bucket{}
				buckets[key] = b
			}
			b.Count++
			b.SumR += int(c.R)
			b.SumG += int(c.G)
			b.SumB += int(c.B)
		}
	}
	if len(buckets) == 0 {
		return primitive.RGB{}, false
	}
	keys := make([][3]uint8, 0, len(buckets))
	for key := range buckets {
		keys = append(keys, key)
	}
	sort.SliceStable(keys, func(i, j int) bool {
		return buckets[keys[i]].Count > buckets[keys[j]].Count
	})
	best := buckets[keys[0]]
	if best.Count < max(10, textBox.Width*textBox.Height/10) {
		return primitive.RGB{}, false
	}
	return primitive.RGB{
		R: uint8(best.SumR / best.Count),
		G: uint8(best.SumG / best.Count),
		B: uint8(best.SumB / best.Count),
	}, true
}

func dominantNonTextColor(img image.Image, search contract.BBox, textBox contract.BBox, textMask mask.Mask) (primitive.RGB, bool) {
	type bucket struct {
		Count int
		SumR  int
		SumG  int
		SumB  int
	}
	buckets := map[[3]uint8]*bucket{}
	for y := search.Y; y < search.Y+search.Height; y += 2 {
		for x := search.X; x < search.X+search.Width; x += 2 {
			if textMask.Get(x, y) || contains(textBox, contract.BBox{X: x, Y: y, Width: 1, Height: 1}, 0) {
				continue
			}
			c := primitive.RGBAt(img, x, y)
			key := [3]uint8{c.R >> 4, c.G >> 4, c.B >> 4}
			b := buckets[key]
			if b == nil {
				b = &bucket{}
				buckets[key] = b
			}
			b.Count++
			b.SumR += int(c.R)
			b.SumG += int(c.G)
			b.SumB += int(c.B)
		}
	}
	if len(buckets) == 0 {
		return primitive.RGB{}, false
	}
	keys := make([][3]uint8, 0, len(buckets))
	for key := range buckets {
		keys = append(keys, key)
	}
	sort.SliceStable(keys, func(i, j int) bool {
		return buckets[keys[i]].Count > buckets[keys[j]].Count
	})
	best := buckets[keys[0]]
	if best.Count < 10 {
		return primitive.RGB{}, false
	}
	return primitive.RGB{
		R: uint8(best.SumR / best.Count),
		G: uint8(best.SumG / best.Count),
		B: uint8(best.SumB / best.Count),
	}, true
}

func detectContrastControlSurfaceCandidate(img image.Image, textBox contract.BBox, search contract.BBox, textMask mask.Mask) (surfaceCandidate, bool) {
	bg, ok := perimeterMedianColor(img, search)
	if !ok {
		return surfaceCandidate{}, false
	}
	localMask := mask.New(textMask.Width, textMask.Height)
	for y := search.Y; y < search.Y+search.Height; y++ {
		for x := search.X; x < search.X+search.Width; x++ {
			if primitive.ColorDistance(primitive.RGBAt(img, x, y), bg) > 14 {
				localMask.Set(x, y, true)
			}
		}
	}
	minArea := max(40, area(textBox)/8)
	var best components.Component
	bestScore := -1
	for _, comp := range components.ConnectedComponents(localMask, minArea, 0.02) {
		if !centerInsideBBox(comp.BBox, textBox, 8) && intersectionRatio(comp.BBox, textBox) < 0.18 {
			continue
		}
		box := trimContrastControlBBox(comp.BBox, textBox)
		if box.Width <= 0 || box.Height <= 0 {
			continue
		}
		score := area(box)
		if score > bestScore {
			bestScore = score
			best = components.Component{BBox: box, Area: comp.Area, Pixels: comp.Pixels}
		}
	}
	if bestScore == -1 {
		return surfaceCandidate{}, false
	}
	return surfaceCandidate{
		BBox:            best.BBox,
		Reasons:         []string{"control_surface_candidate", "contrast_control_surface_candidate"},
		BackgroundColor: meanComponentColor(img, best.Pixels),
	}, true
}

func perimeterMedianColor(img image.Image, box contract.BBox) (primitive.RGB, bool) {
	if box.Width <= 0 || box.Height <= 0 {
		return primitive.RGB{}, false
	}
	var rs, gs, bs []int
	add := func(x, y int) {
		c := primitive.RGBAt(img, x, y)
		rs = append(rs, int(c.R))
		gs = append(gs, int(c.G))
		bs = append(bs, int(c.B))
	}
	for x := box.X; x < box.X+box.Width; x += 2 {
		add(x, box.Y)
		add(x, box.Y+box.Height-1)
	}
	for y := box.Y; y < box.Y+box.Height; y += 2 {
		add(box.X, y)
		add(box.X+box.Width-1, y)
	}
	if len(rs) == 0 {
		return primitive.RGB{}, false
	}
	sort.Ints(rs)
	sort.Ints(gs)
	sort.Ints(bs)
	mid := len(rs) / 2
	return primitive.RGB{R: uint8(rs[mid]), G: uint8(gs[mid]), B: uint8(bs[mid])}, true
}

func trimContrastControlBBox(component contract.BBox, textBox contract.BBox) contract.BBox {
	topPad := max(3, textBox.Height/6)
	bottomPad := max(6, textBox.Height/3)
	y1 := max(component.Y, textBox.Y-topPad)
	y2 := min(component.Y+component.Height, textBox.Y+textBox.Height+bottomPad)
	if y2 <= y1 {
		return contract.BBox{}
	}
	x1 := component.X
	x2 := component.X + component.Width
	if component.Width < 240 && component.Width > textBox.Width+max(32, textBox.Width/2) && component.Width < textBox.Width*3 {
		xPad := max(8, min(16, textBox.Height/2))
		x1 = max(component.X, textBox.X-xPad)
		x2 = min(component.X+component.Width, textBox.X+textBox.Width+xPad)
	}
	if x2 <= x1 {
		return contract.BBox{}
	}
	return contract.BBox{X: x1, Y: y1, Width: x2 - x1, Height: y2 - y1}
}

func meanComponentColor(img image.Image, pixels []components.Point) primitive.RGB {
	if len(pixels) == 0 {
		return primitive.RGB{}
	}
	sumR, sumG, sumB := 0, 0, 0
	for _, p := range pixels {
		c := primitive.RGBAt(img, p.X, p.Y)
		sumR += int(c.R)
		sumG += int(c.G)
		sumB += int(c.B)
	}
	return primitive.RGB{R: uint8(sumR / len(pixels)), G: uint8(sumG / len(pixels)), B: uint8(sumB / len(pixels))}
}

func tightNumericGlyphSurface(text string, surface contract.BBox, textBox contract.BBox) bool {
	if !numericASCIIText(text) {
		return false
	}
	return surface.Width <= textBox.Width+4 && surface.Height <= textBox.Height+4
}

func numericASCIIText(text string) bool {
	if text == "" {
		return false
	}
	count := 0
	for _, r := range text {
		if r == ' ' || r == '\t' || r == '\n' || r == '\r' {
			continue
		}
		if r < '0' || r > '9' {
			return false
		}
		count++
	}
	return count > 0 && count <= 3
}

func centerInsideBBox(parent contract.BBox, child contract.BBox, tolerance int) bool {
	cx := child.X + child.Width/2
	cy := child.Y + child.Height/2
	return parent.X-tolerance <= cx &&
		parent.Y-tolerance <= cy &&
		parent.X+parent.Width+tolerance >= cx &&
		parent.Y+parent.Height+tolerance >= cy
}

func growSurfaceFromSeeds(img image.Image, seeds []surfaceSeed, textMask mask.Mask) contract.BBox {
	if len(seeds) == 0 {
		return contract.BBox{}
	}
	target := seeds[0].Color
	visited := make([]bool, textMask.Width*textMask.Height)
	queue := make([]surfaceSeed, 0, len(seeds))
	for _, seed := range seeds {
		if !textMask.InBounds(seed.X, seed.Y) {
			continue
		}
		idx := seed.Y*textMask.Width + seed.X
		if visited[idx] {
			continue
		}
		if primitive.ColorDistance(primitive.RGBAt(img, seed.X, seed.Y), target) > 42 {
			continue
		}
		visited[idx] = true
		queue = append(queue, seed)
	}
	if len(queue) == 0 {
		return contract.BBox{}
	}
	minX, maxX := queue[0].X, queue[0].X
	minY, maxY := queue[0].Y, queue[0].Y
	head := 0
	for head < len(queue) {
		p := queue[head]
		head++
		if p.X < minX {
			minX = p.X
		}
		if p.X > maxX {
			maxX = p.X
		}
		if p.Y < minY {
			minY = p.Y
		}
		if p.Y > maxY {
			maxY = p.Y
		}
		for _, next := range [...]struct{ X, Y int }{{p.X + 1, p.Y}, {p.X - 1, p.Y}, {p.X, p.Y + 1}, {p.X, p.Y - 1}} {
			if !textMask.InBounds(next.X, next.Y) {
				continue
			}
			idx := next.Y*textMask.Width + next.X
			if visited[idx] {
				continue
			}
			if textMask.Get(next.X, next.Y) {
				continue
			}
			if primitive.ColorDistance(primitive.RGBAt(img, next.X, next.Y), target) > 42 {
				continue
			}
			visited[idx] = true
			queue = append(queue, surfaceSeed{X: next.X, Y: next.Y, Color: target})
		}
	}
	return contract.BBox{X: minX, Y: minY, Width: maxX - minX + 1, Height: maxY - minY + 1}
}

func growControlSurfaceFromSeeds(img image.Image, seeds []surfaceSeed, bounds contract.BBox, textMask mask.Mask) contract.BBox {
	if len(seeds) == 0 || bounds.Width <= 0 || bounds.Height <= 0 {
		return contract.BBox{}
	}
	target := seeds[0].Color
	visited := make([]bool, textMask.Width*textMask.Height)
	queue := make([]surfaceSeed, 0, len(seeds))
	for _, seed := range seeds {
		if !textMask.InBounds(seed.X, seed.Y) || !contains(bounds, contract.BBox{X: seed.X, Y: seed.Y, Width: 1, Height: 1}, 0) {
			continue
		}
		idx := seed.Y*textMask.Width + seed.X
		if visited[idx] {
			continue
		}
		if primitive.ColorDistance(primitive.RGBAt(img, seed.X, seed.Y), target) > 12 {
			continue
		}
		visited[idx] = true
		queue = append(queue, seed)
	}
	if len(queue) == 0 {
		return contract.BBox{}
	}
	minX, maxX := queue[0].X, queue[0].X
	minY, maxY := queue[0].Y, queue[0].Y
	head := 0
	for head < len(queue) {
		p := queue[head]
		head++
		if p.X < minX {
			minX = p.X
		}
		if p.X > maxX {
			maxX = p.X
		}
		if p.Y < minY {
			minY = p.Y
		}
		if p.Y > maxY {
			maxY = p.Y
		}
		for _, next := range [...]struct{ X, Y int }{{p.X + 1, p.Y}, {p.X - 1, p.Y}, {p.X, p.Y + 1}, {p.X, p.Y - 1}} {
			if !textMask.InBounds(next.X, next.Y) || !contains(bounds, contract.BBox{X: next.X, Y: next.Y, Width: 1, Height: 1}, 0) {
				continue
			}
			idx := next.Y*textMask.Width + next.X
			if visited[idx] {
				continue
			}
			if primitive.ColorDistance(primitive.RGBAt(img, next.X, next.Y), target) > 12 {
				continue
			}
			visited[idx] = true
			queue = append(queue, surfaceSeed{X: next.X, Y: next.Y, Color: target})
		}
	}
	return contract.BBox{X: minX, Y: minY, Width: maxX - minX + 1, Height: maxY - minY + 1}
}

func validSurfaceCandidate(surface contract.BBox, textBox contract.BBox, imageWidth int, imageHeight int) bool {
	if surface.Width <= 0 || surface.Height <= 0 {
		return false
	}
	if !contains(surface, textBox, 4) {
		return false
	}
	if surface.Width < textBox.Width+18 || surface.Height < textBox.Height+10 {
		return false
	}
	if surface.Width < 36 || surface.Height < 24 {
		return false
	}
	imageArea := imageWidth * imageHeight
	surfaceArea := area(surface)
	if surfaceArea < max(96, imageArea/30000) {
		return false
	}
	if surfaceArea > imageArea/3 {
		return false
	}
	if touchesImageEdge(surface, imageWidth, imageHeight) && !edgeAnchoredSurface(surface, textBox, imageWidth, imageHeight) {
		return false
	}
	aspect := float64(max(surface.Width, surface.Height)) / float64(max(1, min(surface.Width, surface.Height)))
	return aspect <= 16
}

func validControlSurfaceCandidate(surface contract.BBox, textBox contract.BBox, imageWidth int, imageHeight int) bool {
	if surface.Width <= 0 || surface.Height <= 0 {
		return false
	}
	if !contains(surface, textBox, 4) {
		return false
	}
	if surface.Width < textBox.Width-2 || surface.Height < textBox.Height+2 {
		return false
	}
	if surface.Width < 40 || surface.Height < 24 || surface.Height > 92 {
		return false
	}
	if surface.Width > imageWidth*3/4 || area(surface) > imageWidth*imageHeight/8 {
		return false
	}
	if touchesImageEdge(surface, imageWidth, imageHeight) {
		return false
	}
	aspect := float64(max(surface.Width, surface.Height)) / float64(max(1, min(surface.Width, surface.Height)))
	if aspect > 8 {
		return false
	}
	return true
}

func touchesImageEdge(surface contract.BBox, imageWidth int, imageHeight int) bool {
	return surface.X <= 1 || surface.Y <= 1 || surface.X+surface.Width >= imageWidth-1 || surface.Y+surface.Height >= imageHeight-1
}

func edgeAnchoredSurface(surface contract.BBox, textBox contract.BBox, imageWidth int, imageHeight int) bool {
	if surface.Width < imageWidth/3 && surface.Height < imageHeight/3 {
		return false
	}
	centerX := textBox.X + textBox.Width/2
	centerY := textBox.Y + textBox.Height/2
	inBottomBand := surface.Y+surface.Height >= imageHeight-1 && centerY >= surface.Y
	inTopBand := surface.Y <= 1 && centerY <= surface.Y+surface.Height
	inLeftBand := surface.X <= 1 && centerX <= surface.X+surface.Width
	inRightBand := surface.X+surface.Width >= imageWidth-1 && centerX >= surface.X
	return inBottomBand || inTopBand || inLeftBand || inRightBand
}

func mergeSurfaceCandidates(candidates []surfaceCandidate) []surfaceCandidate {
	var out []surfaceCandidate
	for _, candidate := range candidates {
		merged := false
		for i := range out {
			if !canMergeSurfaceCandidates(out[i], candidate) {
				continue
			}
			if surfaceOverlapRatio(out[i].BBox, candidate.BBox) >= 0.72 || contains(out[i].BBox, candidate.BBox, 6) || contains(candidate.BBox, out[i].BBox, 6) {
				out[i].BBox = unionBBox(out[i].BBox, candidate.BBox)
				out[i].Reasons = appendUnique(out[i].Reasons, candidate.Reasons...)
				merged = true
				break
			}
		}
		if !merged {
			out = append(out, candidate)
		}
	}
	return out
}

func canMergeSurfaceCandidates(a surfaceCandidate, b surfaceCandidate) bool {
	aControl := hasString(a.Reasons, "control_surface_candidate")
	bControl := hasString(b.Reasons, "control_surface_candidate")
	if aControl != bControl {
		return false
	}
	smaller := min(area(a.BBox), area(b.BBox))
	larger := max(area(a.BBox), area(b.BBox))
	if smaller > 0 && larger > smaller*5 {
		return false
	}
	return true
}

func surfaceOverlapRatio(a, b contract.BBox) float64 {
	x1 := max(a.X, b.X)
	y1 := max(a.Y, b.Y)
	x2 := min(a.X+a.Width, b.X+b.Width)
	y2 := min(a.Y+a.Height, b.Y+b.Height)
	intersection := area(contract.BBox{X: x1, Y: y1, Width: x2 - x1, Height: y2 - y1})
	if intersection == 0 {
		return 0
	}
	return float64(intersection) / float64(min(area(a), area(b)))
}

func unionBBox(a, b contract.BBox) contract.BBox {
	x1 := min(a.X, b.X)
	y1 := min(a.Y, b.Y)
	x2 := max(a.X+a.Width, b.X+b.Width)
	y2 := max(a.Y+a.Height, b.Y+b.Height)
	return contract.BBox{X: x1, Y: y1, Width: x2 - x1, Height: y2 - y1}
}

func inflateBBox(b contract.BBox, dx int, dy int, width int, height int) contract.BBox {
	x1 := max(0, b.X-dx)
	y1 := max(0, b.Y-dy)
	x2 := min(width, b.X+b.Width+dx)
	y2 := min(height, b.Y+b.Height+dy)
	return contract.BBox{X: x1, Y: y1, Width: x2 - x1, Height: y2 - y1}
}

func appendUnique(items []string, extra ...string) []string {
	seen := map[string]bool{}
	for _, item := range items {
		seen[item] = true
	}
	for _, item := range extra {
		if !seen[item] {
			items = append(items, item)
			seen[item] = true
		}
	}
	return items
}

func hasString(items []string, value string) bool {
	for _, item := range items {
		if item == value {
			return true
		}
	}
	return false
}

func abs(value int) int {
	if value < 0 {
		return -value
	}
	return value
}
