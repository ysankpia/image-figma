package locator

import (
	"encoding/json"
	"fmt"
	"image"
	"image/draw"
	"os"
	"path/filepath"
	"sort"

	"github.com/luqing-studio/image-figma/tools/go-m29-physical-evidence/internal/m29/components"
	"github.com/luqing-studio/image-figma/tools/go-m29-physical-evidence/internal/m29/contract"
	"github.com/luqing-studio/image-figma/tools/go-m29-physical-evidence/internal/m29/imageio"
	"github.com/luqing-studio/image-figma/tools/go-m29-physical-evidence/internal/m29/mask"
	"github.com/luqing-studio/image-figma/tools/go-m29-physical-evidence/internal/m29/primitive"
)

const OutputName = "m29_locations.v1.json"

type Options struct {
	InputPath string
	OutputDir string
}

func Run(options Options) (contract.Document, error) {
	if options.InputPath == "" {
		return contract.Document{}, fmt.Errorf("missing input path")
	}
	if options.OutputDir == "" {
		return contract.Document{}, fmt.Errorf("missing output dir")
	}

	img, err := imageio.ReadPNG(options.InputPath)
	if err != nil {
		return contract.Document{}, fmt.Errorf("read png: %w", err)
	}
	bounds := img.Bounds()
	width, height := bounds.Dx(), bounds.Dy()
	if width <= 0 || height <= 0 {
		return contract.Document{}, fmt.Errorf("invalid image size")
	}

	cropsDir := filepath.Join(options.OutputDir, "crops")
	if err := os.MkdirAll(cropsDir, 0o755); err != nil {
		return contract.Document{}, err
	}

	bg, threshold := primitive.EstimateBackground(img)
	foreground := buildForegroundMask(img, bg, threshold)
	comps := components.ConnectedComponents(foreground, minComponentArea(width, height), 0.80)
	sort.SliceStable(comps, func(i, j int) bool {
		a, b := comps[i].BBox, comps[j].BBox
		if a.Y != b.Y {
			return a.Y < b.Y
		}
		if a.X != b.X {
			return a.X < b.X
		}
		return comps[i].ID < comps[j].ID
	})

	items := make([]contract.Item, 0, len(comps))
	imageArea := width * height
	for index, comp := range comps {
		id := fmt.Sprintf("loc_%04d", index+1)
		measurements := primitive.MeasureComponent(img, comp, bg)
		kind, hints := primitive.Classify(comp, measurements, imageArea)
		cropPath := filepath.ToSlash(filepath.Join("crops", id+".png"))
		if err := writeCrop(filepath.Join(options.OutputDir, cropPath), img, comp.BBox); err != nil {
			return contract.Document{}, err
		}
		items = append(items, contract.Item{
			ID:           id,
			Kind:         kind,
			BBox:         comp.BBox,
			CropPath:     cropPath,
			Measurements: measurements,
			Hints:        hints,
		})
	}

	doc := contract.Document{
		SchemaName: "M29Locations",
		Version:    "1.0",
		Generator:  contract.Generator{Name: "go-m29", Mode: "m29.0-locator"},
		Image: contract.ImageInfo{
			Width:      width,
			Height:     height,
			SourcePath: options.InputPath,
		},
		Items: items,
		Diagnostics: contract.Diagnostics{
			BackgroundColor:      primitive.Hex(bg),
			ForegroundThreshold:  threshold,
			ForegroundPixelCount: foreground.Count(),
			ComponentCount:       len(comps),
			ItemCount:            len(items),
		},
	}
	data, err := json.MarshalIndent(doc, "", "  ")
	if err != nil {
		return contract.Document{}, err
	}
	if err := os.WriteFile(filepath.Join(options.OutputDir, OutputName), data, 0o644); err != nil {
		return contract.Document{}, err
	}
	return doc, nil
}

func buildForegroundMask(img image.Image, bg primitive.RGB, threshold float64) mask.Mask {
	bounds := img.Bounds()
	out := mask.New(bounds.Dx(), bounds.Dy())
	for y := bounds.Min.Y; y < bounds.Max.Y; y++ {
		for x := bounds.Min.X; x < bounds.Max.X; x++ {
			if primitive.ColorDistance(primitive.RGBAt(img, x, y), bg) > threshold {
				out.Set(x-bounds.Min.X, y-bounds.Min.Y, true)
			}
		}
	}
	return out
}

func minComponentArea(width, height int) int {
	minArea := (width * height) / 90000
	if minArea < 8 {
		return 8
	}
	return minArea
}

func writeCrop(path string, src image.Image, bbox contract.BBox) error {
	if bbox.Width <= 0 || bbox.Height <= 0 {
		return fmt.Errorf("invalid crop bbox")
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	crop := image.NewRGBA(image.Rect(0, 0, bbox.Width, bbox.Height))
	draw.Draw(crop, crop.Bounds(), src, image.Point{X: bbox.X, Y: bbox.Y}, draw.Src)
	return imageio.WritePNG(path, crop)
}
