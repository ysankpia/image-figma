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
	groupNodes := buildGroupNodes(graph, layers)
	emittedGroups := map[string]bool{}
	for _, layer := range layers {
		if !layer.Visible {
			continue
		}
		if layer.GroupID != "" {
			groupNode, ok := groupNodes[layer.GroupID]
			if ok && !emittedGroups[layer.GroupID] {
				root.Children = append(root.Children, groupNode)
				emittedGroups[layer.GroupID] = true
			}
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

func buildGroupNodes(graph contract.Document, layers []contract.Layer) map[string]Node {
	layersByID := map[string]contract.Layer{}
	for _, layer := range layers {
		layersByID[layer.ID] = layer
	}
	out := map[string]Node{}
	for _, group := range graph.Groups {
		children := make([]Node, 0, len(group.ChildLayerIDs))
		minZ := 0
		for _, id := range group.ChildLayerIDs {
			layer, ok := layersByID[id]
			if !ok || !layer.Visible || layer.GroupID != group.ID {
				continue
			}
			child := nodeFromLayer(layer)
			child.BBox = localBBox(child.BBox, group.BBox)
			children = append(children, child)
			if minZ == 0 || layer.Z < minZ {
				minZ = layer.Z
			}
		}
		if len(children) == 0 {
			continue
		}
		sort.SliceStable(children, func(i, j int) bool {
			if children[i].Z != children[j].Z {
				return children[i].Z < children[j].Z
			}
			return children[i].ID < children[j].ID
		})
		visible := true
		out[group.ID] = Node{
			ID:      group.ID,
			Type:    "group",
			Name:    "Group / " + group.ID,
			BBox:    group.BBox,
			Z:       minZ,
			Visible: &visible,
			Style: map[string]any{
				"fill":        nil,
				"clipContent": false,
			},
			Children: children,
			Meta: map[string]any{
				"layerKind":    contract.LayerGroup,
				"semanticTags": group.SemanticTags,
				"decision":     group.Decision,
			},
		}
	}
	return out
}

func localBBox(box, parent geometry.Rect) geometry.Rect {
	return geometry.Rect{
		X:      box.X - parent.X,
		Y:      box.Y - parent.Y,
		Width:  box.Width,
		Height: box.Height,
	}
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
