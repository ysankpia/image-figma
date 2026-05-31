package exportdsl

import (
	"encoding/json"
	"os"
	"path/filepath"
	"sort"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/draft/contract"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/image/geometry"
)

const ArtifactName = "draft_runtime.dsl.v1.json"

func Export(taskID string, graph contract.Document) Document {
	root := Node{
		ID:   "root",
		Type: "frame",
		Name: "Draft",
		BBox: graphImageBBox(graph.Image),
		Meta: map[string]any{
			"sourceContract": graph.Version,
		},
	}

	layers := append([]contract.Layer(nil), graph.Layers...)
	sort.SliceStable(layers, func(i, j int) bool {
		if layers[i].Z != layers[j].Z {
			return layers[i].Z < layers[j].Z
		}
		return layers[i].ID < layers[j].ID
	})
	for _, layer := range layers {
		if !layer.Visible {
			continue
		}
		root.Children = append(root.Children, nodeFromLayer(layer))
	}

	assets := make([]Asset, 0, len(graph.Assets))
	for _, asset := range graph.Assets {
		assets = append(assets, Asset{
			AssetID: asset.ID,
			Type:    asset.Type,
			URL:     asset.URL,
			Path:    asset.Path,
			Format:  asset.Format,
			Width:   asset.Width,
			Height:  asset.Height,
		})
	}

	return Document{
		Version: Version,
		Kind:    Kind,
		TaskID:  taskID,
		Page: Page{
			Name:   "Draft",
			Width:  graph.Image.Width,
			Height: graph.Image.Height,
		},
		Assets: assets,
		Root:   root,
	}
}

func WriteArtifact(outputDir string, doc Document) error {
	if err := os.MkdirAll(outputDir, 0o755); err != nil {
		return err
	}
	data, err := json.MarshalIndent(doc, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(filepath.Join(outputDir, ArtifactName), append(data, '\n'), 0o644)
}

func graphImageBBox(image contract.ImageMeta) geometry.Rect {
	return geometry.Rect{Width: image.Width, Height: image.Height}
}

func nodeFromLayer(layer contract.Layer) Node {
	visible := layer.Visible
	node := Node{
		ID:      layer.ID,
		Type:    nodeType(layer.Kind),
		Name:    layer.Name,
		BBox:    layer.BBox,
		Z:       layer.Z,
		Visible: &visible,
		Meta: map[string]any{
			"layerKind":    layer.Kind,
			"semanticTags": layer.SemanticTags,
			"sourceRefs":   layer.SourceRefs,
			"decision":     layer.Decision,
		},
	}
	if layer.Text != nil {
		node.Text = &Text{Characters: layer.Text.Characters}
	}
	if layer.Raster != nil {
		node.Image = &Image{AssetID: layer.Raster.AssetID, Mode: layer.Raster.Mode}
	}
	if layer.Shape != nil {
		node.Style = map[string]any{
			"fill":         layer.Shape.Fill,
			"stroke":       layer.Shape.Stroke,
			"cornerRadius": layer.Shape.CornerRadius,
			"opacity":      layer.Shape.Opacity,
		}
	}
	return node
}

func nodeType(kind contract.LayerKind) string {
	switch kind {
	case contract.LayerText:
		return "text"
	case contract.LayerRaster, contract.LayerReferenceImage:
		return "image"
	case contract.LayerShape:
		return "shape"
	case contract.LayerGroup:
		return "group"
	default:
		return "frame"
	}
}
