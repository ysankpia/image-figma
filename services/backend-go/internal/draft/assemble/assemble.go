package assemble

import (
	"fmt"
	"sort"
	"strings"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/draft/contract"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/image/geometry"
	m29contract "github.com/luqing-studio/image-figma/services/backend-go/internal/m29/contract"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/evidence"
)

type Input struct {
	Image  contract.ImageMeta
	Tokens evidence.Document
}

func Build(input Input) (contract.Document, error) {
	if input.Image.Width <= 0 || input.Image.Height <= 0 {
		return contract.Document{}, fmt.Errorf("invalid image size")
	}
	layers := []contract.Layer{{
		ID:      "reference_image",
		Kind:    contract.LayerReferenceImage,
		BBox:    imageBBox(input.Image),
		Z:       -1,
		Visible: false,
		Locked:  true,
		Name:    "Reference Image",
		Decision: contract.Decision{
			State:         contract.DecisionReferenceOnly,
			BBoxAuthority: contract.BBoxAuthoritySourceImage,
			Reason:        "hidden_source_reference",
		},
	}}
	assets := []contract.Asset{}

	tokens := append([]evidence.Token(nil), input.Tokens.Tokens...)
	sort.SliceStable(tokens, func(i, j int) bool {
		a, b := toRect(tokens[i].BBox), toRect(tokens[j].BBox)
		if a.Y != b.Y {
			return a.Y < b.Y
		}
		if a.X != b.X {
			return a.X < b.X
		}
		return tokens[i].ID < tokens[j].ID
	})

	nextLayer := 1
	nextAsset := 1
	for _, token := range tokens {
		if token.Disposition != "main" {
			continue
		}
		box := geometry.Clamp(toRect(token.BBox), imageBBox(input.Image))
		if box.Empty() {
			continue
		}
		switch token.TokenType {
		case "surface_region_token", "layer_background_token", "line_token":
			layer := baseLayer(nextLayer, contract.LayerShape, box, 10_000+nextLayer, token)
			layer.Name = nameForLayer(layer.Kind, nextLayer)
			layer.Shape = &contract.Shape{
				Fill:         firstNonEmpty(token.Measurements.MeanColor, "#E5E7EB"),
				CornerRadius: token.Measurements.CornerRadiusEstimate,
				Opacity:      1,
			}
			layers = append(layers, layer)
			nextLayer++
		case "raster_region_token", "symbol_cluster_token":
			if !emitRasterToken(input.Image, token) {
				continue
			}
			assetID := fmt.Sprintf("asset_raster_%04d", nextAsset)
			nextAsset++
			layer := baseLayer(nextLayer, contract.LayerRaster, box, 20_000+nextLayer, token)
			layer.Name = nameForLayer(layer.Kind, nextLayer)
			layer.Raster = &contract.Raster{AssetID: assetID, Mode: "fill"}
			layer.SemanticTags = rasterTags(token)
			asset := contract.Asset{
				ID:         assetID,
				Type:       "image",
				Path:       fmt.Sprintf("assets/%s.png", assetID),
				URL:        fmt.Sprintf("assets/%s.png", assetID),
				Format:     "png",
				BBox:       box,
				Width:      box.Width,
				Height:     box.Height,
				SourceRefs: sourceRefs(token),
			}
			layers = append(layers, layer)
			assets = append(assets, asset)
			nextLayer++
		case "text_token":
			text := strings.TrimSpace(token.Content.Text)
			if text == "" {
				continue
			}
			layer := baseLayer(nextLayer, contract.LayerText, box, 30_000+nextLayer, token)
			layer.Name = nameForLayer(layer.Kind, nextLayer)
			layer.Text = &contract.Text{Characters: text}
			layer.Decision.BBoxAuthority = contract.BBoxAuthorityOCR
			layers = append(layers, layer)
			nextLayer++
		}
	}

	return contract.Document{
		Version: contract.Version,
		Image:   input.Image,
		Layers:  layers,
		Assets:  assets,
		Summary: summarize(layers, nil, assets),
	}, nil
}

func imageBBox(image contract.ImageMeta) geometry.Rect {
	return geometry.Rect{Width: image.Width, Height: image.Height}
}

func summarize(layers []contract.Layer, groups []contract.Group, assets []contract.Asset) contract.Summary {
	counts := map[string]int{}
	for _, layer := range layers {
		counts[string(layer.Kind)]++
	}
	return contract.Summary{
		LayerCount: len(layers),
		GroupCount: len(groups),
		AssetCount: len(assets),
		KindCounts: counts,
	}
}

func baseLayer(index int, kind contract.LayerKind, box geometry.Rect, z int, token evidence.Token) contract.Layer {
	return contract.Layer{
		ID:         fmt.Sprintf("layer_%04d", index),
		Kind:       kind,
		BBox:       box,
		Z:          z,
		Visible:    true,
		SourceRefs: sourceRefs(token),
		Decision: contract.Decision{
			State:         contract.DecisionEmit,
			BBoxAuthority: contract.BBoxAuthorityM29,
			Reason:        decisionReason(token),
			SourceIDs:     append([]string(nil), token.SourcePrimitiveIDs...),
		},
	}
}

func nameForLayer(kind contract.LayerKind, index int) string {
	switch kind {
	case contract.LayerText:
		return fmt.Sprintf("Text %04d", index)
	case contract.LayerRaster:
		return fmt.Sprintf("Raster %04d", index)
	case contract.LayerShape:
		return fmt.Sprintf("Shape %04d", index)
	default:
		return fmt.Sprintf("Layer %04d", index)
	}
}

func sourceRefs(token evidence.Token) []contract.SourceRef {
	refs := []contract.SourceRef{{Kind: "m29_token", ID: token.ID}}
	for _, id := range token.SourcePrimitiveIDs {
		if id != "" {
			refs = append(refs, contract.SourceRef{Kind: "m29_primitive", ID: id})
		}
	}
	return refs
}

func decisionReason(token evidence.Token) string {
	if len(token.Reasons) == 0 {
		return token.TokenType
	}
	return strings.Join(token.Reasons, "+")
}

func rasterTags(token evidence.Token) []string {
	if token.TokenType == "symbol_cluster_token" || token.CompileHints.CanBeIcon {
		return []string{"icon_candidate"}
	}
	if token.CompileHints.CanBeImage {
		return []string{"image_candidate"}
	}
	return nil
}

func emitRasterToken(image contract.ImageMeta, token evidence.Token) bool {
	box := toRect(token.BBox)
	if box.Empty() {
		return false
	}
	imageArea := max(1, image.Width*image.Height)
	boxArea := box.Area()
	if boxArea*100 >= imageArea*72 {
		return false
	}
	if box.Width*100 >= image.Width*92 && box.Height*100 >= image.Height*50 {
		return false
	}
	if token.TokenType == "symbol_cluster_token" {
		return token.CompileHints.CanBeIcon || token.Measurements.PrimitiveCount > 1
	}
	return token.CompileHints.CanBeImage || hasReason(token, "raster_region") || hasReason(token, "large_textured_symbol_as_raster")
}

func hasReason(token evidence.Token, reason string) bool {
	for _, item := range token.Reasons {
		if item == reason {
			return true
		}
	}
	for _, item := range token.CompileHints.Reasons {
		if item == reason {
			return true
		}
	}
	return false
}

func toRect(box m29contract.BBox) geometry.Rect {
	return geometry.Rect{X: box.X, Y: box.Y, Width: box.Width, Height: box.Height}
}

func firstNonEmpty(values ...string) string {
	for _, value := range values {
		if strings.TrimSpace(value) != "" {
			return strings.TrimSpace(value)
		}
	}
	return ""
}

func max(a, b int) int {
	if a > b {
		return a
	}
	return b
}
