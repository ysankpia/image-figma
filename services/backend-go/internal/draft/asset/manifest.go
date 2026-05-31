package asset

import (
	"encoding/json"
	"fmt"
	"image"
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
	for _, asset := range doc.Assets {
		if asset.Type != "image" || asset.ID == "" {
			continue
		}
		crop, err := cropImage(src, asset.BBox)
		if err != nil {
			return fmt.Errorf("crop draft asset %s: %w", asset.ID, err)
		}
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

func clamp(value, low, high int) int {
	if value < low {
		return low
	}
	if value > high {
		return high
	}
	return value
}
