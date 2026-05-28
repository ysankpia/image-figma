package pipeline

import (
	"context"
	"encoding/json"
	"fmt"
	"image"
	"image/draw"
	"os"
	"path/filepath"
	"sort"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/components"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/config"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/contract"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/debug"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/imageio"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/mask"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/ocr"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/primitive"
)

type Options struct {
	InputPath   string
	OCRPath     string
	OCRProvider string
	OutputDir   string
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
	if err := os.MkdirAll(filepath.Join(options.OutputDir, "masks"), 0o755); err != nil {
		return contract.Document{}, err
	}
	if err := os.MkdirAll(filepath.Join(options.OutputDir, "crops"), 0o755); err != nil {
		return contract.Document{}, err
	}

	var ocrDoc ocr.Document
	ocrProvided := false
	if options.OCRPath != "" {
		ocrDoc, err = ocr.Read(options.OCRPath)
		if err != nil {
			return contract.Document{}, fmt.Errorf("read ocr: %w", err)
		}
		ocrProvided = true
	} else {
		ocrConfig := config.OCRFromEnv(options.OCRProvider)
		if ocrConfig.Provider == "baidu_ppocrv5" {
			ocrDoc, err = ocr.ExtractBaiduPPOCRV5(
				context.Background(),
				options.InputPath,
				ocr.ImageInfo{Width: width, Height: height},
				ocrConfig,
			)
			if err != nil {
				return contract.Document{}, fmt.Errorf("baidu ppocrv5: %w", err)
			}
			ocrProvided = true
		} else if ocrConfig.Provider != "" && ocrConfig.Provider != "none" && ocrConfig.Provider != "fake" {
			return contract.Document{}, fmt.Errorf("unsupported ocr provider %q", ocrConfig.Provider)
		}
	}
	if ocrProvided {
		if err := ocr.Write(filepath.Join(options.OutputDir, "ocr.json"), ocrDoc); err != nil {
			return contract.Document{}, fmt.Errorf("write ocr: %w", err)
		}
	}

	bg, threshold := primitive.EstimateBackground(img)
	textMask := mask.New(width, height)
	for _, block := range ocrDoc.Blocks {
		mask.FillBBox(textMask, block.BBox, 2)
	}
	foreground := buildForegroundMask(img, bg, threshold, textMask)
	comps := components.ConnectedComponents(foreground, minComponentArea(width, height), 0.80)

	var primitives []contract.Primitive
	var assets []contract.Asset
	nextID := 1
	for _, block := range ocrDoc.Blocks {
		id := fmt.Sprintf("prim_%04d", nextID)
		nextID++
		maskRef, cropRef, blockAssets, err := writePrimitiveArtifacts(options.OutputDir, id, img, mask.BBoxMask(width, height, block.BBox), block.BBox)
		if err != nil {
			return contract.Document{}, err
		}
		assets = append(assets, blockAssets...)
		primitives = append(primitives, contract.Primitive{
			ID:            id,
			PrimitiveType: "text_region",
			BBox:          block.BBox,
			MaskRef:       maskRef,
			CropRef:       cropRef,
			Source:        contract.Source{Kind: "ocr", OCRBlockID: block.ID, Text: block.Text},
			Measurements:  primitive.MeasureOCRBlock(img, block.BBox, bg),
			CompileHints:  primitive.OCRHint(),
		})
	}

	for _, surface := range detectSurfaceCandidates(img, ocrDoc.Blocks, textMask) {
		id := fmt.Sprintf("prim_%04d", nextID)
		nextID++
		surfaceMask := mask.BBoxMask(width, height, surface.BBox)
		maskRef, cropRef, surfaceAssets, err := writePrimitiveArtifacts(options.OutputDir, id, img, surfaceMask, surface.BBox)
		if err != nil {
			return contract.Document{}, err
		}
		assets = append(assets, surfaceAssets...)
		primitives = append(primitives, contract.Primitive{
			ID:            id,
			PrimitiveType: "surface_region",
			BBox:          surface.BBox,
			MaskRef:       maskRef,
			CropRef:       cropRef,
			Source:        contract.Source{Kind: "pixel"},
			Measurements:  primitive.MeasureSurface(img, surface.BBox, bg),
			CompileHints:  primitive.SurfaceHint(surface.Reasons),
		})
	}

	imageArea := width * height
	for _, comp := range comps {
		id := fmt.Sprintf("prim_%04d", nextID)
		nextID++
		measurements := primitive.MeasureComponent(img, comp, bg)
		primitiveType, hints := primitive.Classify(comp, measurements, imageArea)
		componentMask := componentMask(width, height, comp)
		maskRef, cropRef, compAssets, err := writePrimitiveArtifacts(options.OutputDir, id, img, componentMask, comp.BBox)
		if err != nil {
			return contract.Document{}, err
		}
		assets = append(assets, compAssets...)
		primitives = append(primitives, contract.Primitive{
			ID:            id,
			PrimitiveType: primitiveType,
			BBox:          comp.BBox,
			MaskRef:       maskRef,
			CropRef:       cropRef,
			Source:        contract.Source{Kind: "pixel"},
			Measurements:  measurements,
			CompileHints:  hints,
		})
	}
	sort.SliceStable(primitives, func(i, j int) bool {
		a, b := primitives[i].BBox, primitives[j].BBox
		if a.Y != b.Y {
			return a.Y < b.Y
		}
		if a.X != b.X {
			return a.X < b.X
		}
		return primitives[i].ID < primitives[j].ID
	})

	relations := buildRelations(primitives)
	doc := contract.Document{
		SchemaName:        "M29PhysicalEvidence",
		Version:           "1.0",
		Generator:         contract.Generator{Name: "go-m29", Mode: "purego"},
		Image:             contract.ImageInfo{Width: width, Height: height, SourcePath: options.InputPath},
		OCR:               contract.OCRInfo{Provided: ocrProvided, BlockCount: len(ocrDoc.Blocks)},
		Primitives:        primitives,
		PhysicalRelations: relations,
		Assets:            assets,
		Diagnostics: contract.Diagnostics{
			BackgroundColor:      primitive.Hex(bg),
			ForegroundThreshold:  threshold,
			ForegroundPixelCount: foreground.Count(),
			ComponentCount:       len(comps),
			PrimitiveCount:       len(primitives),
			TextMaskPixelCount:   textMask.Count(),
		},
	}
	if err := debug.WriteOverlay(filepath.Join(options.OutputDir, "debug_overlay.png"), img, primitives); err != nil {
		return contract.Document{}, err
	}
	if err := debug.WritePreviewSheet(filepath.Join(options.OutputDir, "preview_sheet.png"), img, filepath.Join(options.OutputDir, "debug_overlay.png")); err != nil {
		return contract.Document{}, err
	}
	data, err := json.MarshalIndent(doc, "", "  ")
	if err != nil {
		return contract.Document{}, err
	}
	if err := os.WriteFile(filepath.Join(options.OutputDir, "m29_physical_evidence.v1.json"), data, 0o644); err != nil {
		return contract.Document{}, err
	}
	return doc, nil
}

func buildForegroundMask(img image.Image, bg primitive.RGB, threshold float64, textMask mask.Mask) mask.Mask {
	bounds := img.Bounds()
	out := mask.New(bounds.Dx(), bounds.Dy())
	for y := bounds.Min.Y; y < bounds.Max.Y; y++ {
		for x := bounds.Min.X; x < bounds.Max.X; x++ {
			lx, ly := x-bounds.Min.X, y-bounds.Min.Y
			if textMask.Get(lx, ly) {
				continue
			}
			if primitive.ColorDistance(primitive.RGBAt(img, x, y), bg) > threshold {
				out.Set(lx, ly, true)
			}
		}
	}
	return out
}

func componentMask(width, height int, comp components.Component) mask.Mask {
	m := mask.New(width, height)
	for _, p := range comp.Pixels {
		m.Set(p.X, p.Y, true)
	}
	return m
}

func writePrimitiveArtifacts(outputDir, id string, img image.Image, m mask.Mask, bbox contract.BBox) (string, string, []contract.Asset, error) {
	maskRef := filepath.ToSlash(filepath.Join("masks", id+".png"))
	cropRef := filepath.ToSlash(filepath.Join("crops", id+".png"))
	if err := debug.WriteMaskPNG(filepath.Join(outputDir, maskRef), m); err != nil {
		return "", "", nil, err
	}
	if err := writeCrop(filepath.Join(outputDir, cropRef), img, bbox); err != nil {
		return "", "", nil, err
	}
	return maskRef, cropRef, []contract.Asset{
		{ID: id + "_mask", PrimitiveID: id, Kind: "mask", Path: maskRef},
		{ID: id + "_crop", PrimitiveID: id, Kind: "crop", Path: cropRef},
	}, nil
}

func writeCrop(path string, img image.Image, bbox contract.BBox) error {
	bounds := img.Bounds()
	x1 := max(bounds.Min.X, bbox.X)
	y1 := max(bounds.Min.Y, bbox.Y)
	x2 := min(bounds.Max.X, bbox.X+bbox.Width)
	y2 := min(bounds.Max.Y, bbox.Y+bbox.Height)
	if x2 <= x1 || y2 <= y1 {
		return fmt.Errorf("invalid crop bbox")
	}
	dst := image.NewRGBA(image.Rect(0, 0, x2-x1, y2-y1))
	draw.Draw(dst, dst.Bounds(), img, image.Point{X: x1, Y: y1}, draw.Src)
	return imageio.WritePNG(path, dst)
}

func minComponentArea(width, height int) int {
	area := width * height
	minArea := area / 90000
	if minArea < 8 {
		return 8
	}
	return minArea
}
