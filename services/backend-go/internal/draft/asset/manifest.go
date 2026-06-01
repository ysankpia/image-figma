package asset

import (
	"encoding/json"
	"fmt"
	"image"
	"image/color"
	"image/draw"
	"os"
	"path/filepath"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/draft/contract"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/image/geometry"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/imageio"
)

const ManifestName = "asset_manifest.json"

type Manifest struct {
	Version string           `json:"version"`
	Assets  []contract.Asset `json:"assets"`
}

func FromGraph(doc contract.Document) Manifest {
	return Manifest{
		Version: "draft_asset_manifest.v1",
		Assets:  append([]contract.Asset(nil), doc.Assets...),
	}
}

func WriteManifest(dir string, manifest Manifest) error {
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return err
	}
	data, err := json.MarshalIndent(manifest, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(filepath.Join(dir, ManifestName), append(data, '\n'), 0o644)
}

func WriteLayerAssets(dir string, sourcePath string, doc contract.Document) error {
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return err
	}
	src, err := imageio.ReadPNG(sourcePath)
	if err != nil {
		return fmt.Errorf("read source png for draft assets: %w", err)
	}
	textBoxes := collectTextBoxes(doc)
	for _, asset := range doc.Assets {
		if asset.Type != "image" || asset.ID == "" {
			continue
		}
		crop, err := cropImage(src, asset.BBox)
		if err != nil {
			return fmt.Errorf("crop draft asset %s: %w", asset.ID, err)
		}
		eraseTextRegions(crop.(*image.RGBA), asset.BBox, textBoxes, src)
		if err := imageio.WritePNG(filepath.Join(dir, asset.ID+".png"), crop); err != nil {
			return fmt.Errorf("write draft asset %s: %w", asset.ID, err)
		}
	}
	return nil
}

func cropImage(src image.Image, bbox geometry.Rect) (image.Image, error) {
	bounds := src.Bounds()
	x1 := clamp(bbox.X, 0, bounds.Dx())
	y1 := clamp(bbox.Y, 0, bounds.Dy())
	x2 := clamp(bbox.Right(), x1+1, bounds.Dx())
	y2 := clamp(bbox.Bottom(), y1+1, bounds.Dy())
	if x2 <= x1 || y2 <= y1 {
		return nil, fmt.Errorf("invalid bbox")
	}
	rect := image.Rect(0, 0, x2-x1, y2-y1)
	out := image.NewRGBA(rect)
	draw.Draw(out, rect, src, image.Pt(bounds.Min.X+x1, bounds.Min.Y+y1), draw.Src)
	return out, nil
}

func collectTextBoxes(doc contract.Document) []geometry.Rect {
	var boxes []geometry.Rect
	for _, layer := range doc.Layers {
		if layer.Visible && layer.Kind == contract.LayerText {
			boxes = append(boxes, layer.BBox)
		}
	}
	return boxes
}

func eraseTextRegions(crop *image.RGBA, cropBBox geometry.Rect, textBoxes []geometry.Rect, src image.Image) {
	for _, tb := range textBoxes {
		overlap := intersect(cropBBox, tb)
		if overlap.Width <= 0 || overlap.Height <= 0 {
			continue
		}
		localX := overlap.X - cropBBox.X
		localY := overlap.Y - cropBBox.Y
		fill := sampleBorderColor(src, tb)
		for y := localY; y < localY+overlap.Height; y++ {
			for x := localX; x < localX+overlap.Width; x++ {
				if x >= 0 && y >= 0 && x < crop.Bounds().Dx() && y < crop.Bounds().Dy() {
					crop.SetRGBA(x, y, fill)
				}
			}
		}
	}
}

func sampleBorderColor(src image.Image, bbox geometry.Rect) color.RGBA {
	bounds := src.Bounds()
	var rSum, gSum, bSum, count uint32
	for x := bbox.X; x < bbox.X+bbox.Width; x++ {
		for _, y := range []int{bbox.Y - 1, bbox.Y + bbox.Height} {
			if x >= bounds.Min.X && x < bounds.Max.X && y >= bounds.Min.Y && y < bounds.Max.Y {
				r, g, b, _ := src.At(x, y).RGBA()
				rSum += r >> 8
				gSum += g >> 8
				bSum += b >> 8
				count++
			}
		}
	}
	for y := bbox.Y; y < bbox.Y+bbox.Height; y++ {
		for _, x := range []int{bbox.X - 1, bbox.X + bbox.Width} {
			if x >= bounds.Min.X && x < bounds.Max.X && y >= bounds.Min.Y && y < bounds.Max.Y {
				r, g, b, _ := src.At(x, y).RGBA()
				rSum += r >> 8
				gSum += g >> 8
				bSum += b >> 8
				count++
			}
		}
	}
	if count == 0 {
		return color.RGBA{R: 255, G: 255, B: 255, A: 255}
	}
	return color.RGBA{
		R: uint8(rSum / count),
		G: uint8(gSum / count),
		B: uint8(bSum / count),
		A: 255,
	}
}

func intersect(a, b geometry.Rect) geometry.Rect {
	x1 := max(a.X, b.X)
	y1 := max(a.Y, b.Y)
	x2 := min(a.Right(), b.Right())
	y2 := min(a.Bottom(), b.Bottom())
	if x2 <= x1 || y2 <= y1 {
		return geometry.Rect{}
	}
	return geometry.Rect{X: x1, Y: y1, Width: x2 - x1, Height: y2 - y1}
}

func max(a, b int) int {
	if a > b {
		return a
	}
	return b
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}

func clamp(value, low, high int) int {
	if value < low {
		return low
	}
	if value > high {
		return high
	}
	return value
}
