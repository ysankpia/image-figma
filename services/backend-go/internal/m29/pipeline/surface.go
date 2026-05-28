package pipeline

import (
	"image"
	"sort"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/contract"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/mask"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/ocr"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/primitive"
)

type surfaceCandidate struct {
	BBox    contract.BBox
	Reasons []string
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
			BBox:    box,
			Reasons: []string{"ocr_anchored_low_texture_surface", "local_surface_color_region"},
		})
	}
	return mergeSurfaceCandidates(candidates)
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
	if surface.X <= 1 || surface.Y <= 1 || surface.X+surface.Width >= imageWidth-1 || surface.Y+surface.Height >= imageHeight-1 {
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
	aspect := float64(max(surface.Width, surface.Height)) / float64(max(1, min(surface.Width, surface.Height)))
	return aspect <= 16
}

func mergeSurfaceCandidates(candidates []surfaceCandidate) []surfaceCandidate {
	var out []surfaceCandidate
	for _, candidate := range candidates {
		merged := false
		for i := range out {
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
