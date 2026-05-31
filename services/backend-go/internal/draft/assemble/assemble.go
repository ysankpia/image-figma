package assemble

import (
	"github.com/luqing-studio/image-figma/services/backend-go/internal/draft/contract"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/image/geometry"
)

type Input struct {
	Image contract.ImageMeta
}

func Build(input Input) (contract.Document, error) {
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
	return contract.Document{
		Version: contract.Version,
		Image:   input.Image,
		Layers:  layers,
		Summary: summarize(layers, nil, nil),
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
