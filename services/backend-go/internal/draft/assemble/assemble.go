package assemble

import (
	"fmt"
	"math"
	"sort"
	"strings"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/draft/contract"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/image/geometry"
	m29contract "github.com/luqing-studio/image-figma/services/backend-go/internal/m29/contract"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/evidence"
	visiondetector "github.com/luqing-studio/image-figma/services/backend-go/internal/vision/detector"
)

type Input struct {
	Image    contract.ImageMeta
	Tokens   evidence.Document
	Detector *visiondetector.Document
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
	decisionEvidence := []contract.Evidence{}

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
			layer.Text = &contract.Text{
				Characters: text,
				FontSize:   estimateFontSize(box.Height, box.Width, len([]rune(text))),
			}
			layer.Decision.BBoxAuthority = contract.BBoxAuthorityOCR
			layers = append(layers, layer)
			nextLayer++
		}
	}

	layers, assets, decisionEvidence, nextLayer, nextAsset = appendVisionImageCandidates(input.Image, input.Detector, layers, assets, decisionEvidence, nextLayer, nextAsset)
	layers, assets = suppressM29CoveredByVision(layers, assets)
	layers, assets = suppressDuplicateVisibleOwners(input.Image, layers, assets)
	groups := buildMajorGroups(input.Image, layers)
	layers = applyLayerGroups(layers, groups)

	return contract.Document{
		Version:  contract.Version,
		Image:    input.Image,
		Layers:   layers,
		Groups:   groups,
		Assets:   assets,
		Evidence: decisionEvidence,
		Summary:  summarize(layers, groups, assets),
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

func appendVisionImageCandidates(image contract.ImageMeta, doc *visiondetector.Document, layers []contract.Layer, assets []contract.Asset, evidenceItems []contract.Evidence, nextLayer, nextAsset int) ([]contract.Layer, []contract.Asset, []contract.Evidence, int, int) {
	if doc == nil {
		return layers, assets, evidenceItems, nextLayer, nextAsset
	}
	candidates := append([]visiondetector.Candidate(nil), doc.Candidates...)
	sort.SliceStable(candidates, func(i, j int) bool {
		if candidates[i].Confidence != candidates[j].Confidence {
			return candidates[i].Confidence > candidates[j].Confidence
		}
		if candidates[i].BBox.Y != candidates[j].BBox.Y {
			return candidates[i].BBox.Y < candidates[j].BBox.Y
		}
		if candidates[i].BBox.X != candidates[j].BBox.X {
			return candidates[i].BBox.X < candidates[j].BBox.X
		}
		return candidates[i].ID < candidates[j].ID
	})
	for _, candidate := range candidates {
		box := geometry.Clamp(visionBBoxToRect(candidate.BBox), imageBBox(image))
		item := contract.Evidence{
			ID:            "vision_" + candidate.ID,
			Kind:          "vision_detector_candidate",
			BBox:          box,
			BBoxAuthority: contract.BBoxAuthorityVision,
			SourceRefs:    []contract.SourceRef{{Kind: "vision_detector_candidate", ID: candidate.ID}},
			Reason:        "vision_hint_only:" + string(candidate.Role),
			Score:         candidate.Confidence,
			Meta: map[string]any{
				"role":   candidate.Role,
				"passId": candidate.Source.PassID,
				"label":  candidate.RawLabel,
				"merge":  candidate.Merge,
				"source": candidate.Source,
			},
		}
		switch candidate.Role {
		case visiondetector.RoleBackground:
			if !canEmitVisionBackground(candidate, box, layers) {
				item.State = contract.DecisionSuppress
				item.Reason = "vision_background_rejected"
				evidenceItems = append(evidenceItems, item)
				continue
			}
			layer := contract.Layer{
				ID:           fmt.Sprintf("vision_bg_%04d", nextLayer),
				Kind:         contract.LayerShape,
				BBox:         box,
				Z:            10_000 + nextLayer,
				Visible:      true,
				Name:         fmt.Sprintf("Shape Vision %04d", nextLayer),
				SemanticTags: []string{"vision_background_candidate"},
				Shape:        &contract.Shape{Fill: "#E5E7EB", CornerRadius: 0, Opacity: 1},
				SourceRefs:   []contract.SourceRef{{Kind: "vision_detector_candidate", ID: candidate.ID}},
				Decision: contract.Decision{
					State:         contract.DecisionEmit,
					BBoxAuthority: contract.BBoxAuthorityVision,
					Reason:        "vision_background_candidate",
					SourceIDs:     []string{candidate.ID},
				},
			}
			layers = append(layers, layer)
			item.State = contract.DecisionEmit
			item.Reason = "vision_background_candidate"
			item.LayerID = layer.ID
			evidenceItems = append(evidenceItems, item)
			nextLayer++
		case visiondetector.RoleImageView:
			if !canEmitVisionImage(image, candidate, box, layers) {
				item.State = contract.DecisionSuppress
				item.Reason = "vision_image_rejected_by_compact_or_duplicate_gate"
				evidenceItems = append(evidenceItems, item)
				continue
			}
			assetID := fmt.Sprintf("asset_vision_%04d", nextAsset)
			nextAsset++
			layer := contract.Layer{
				ID:           fmt.Sprintf("vision_image_%04d", nextLayer),
				Kind:         contract.LayerRaster,
				BBox:         box,
				Z:            20_000 + nextLayer,
				Visible:      true,
				Name:         fmt.Sprintf("Raster Vision %04d", nextLayer),
				SemanticTags: []string{"vision_image_candidate"},
				Raster:       &contract.Raster{AssetID: assetID, Mode: "fill"},
				SourceRefs:   []contract.SourceRef{{Kind: "vision_detector_candidate", ID: candidate.ID}},
				Decision: contract.Decision{
					State:         contract.DecisionEmit,
					BBoxAuthority: contract.BBoxAuthorityVision,
					Reason:        "vision_compact_image_candidate",
					SourceIDs:     []string{candidate.ID},
				},
			}
			layers = append(layers, layer)
			assets = append(assets, contract.Asset{
				ID:         assetID,
				Type:       "image",
				Path:       fmt.Sprintf("assets/%s.png", assetID),
				URL:        fmt.Sprintf("assets/%s.png", assetID),
				Format:     "png",
				BBox:       box,
				Width:      box.Width,
				Height:     box.Height,
				SourceRefs: layer.SourceRefs,
			})
			item.State = contract.DecisionEmit
			item.Reason = "vision_compact_image_candidate"
			item.LayerID = layer.ID
			evidenceItems = append(evidenceItems, item)
			nextLayer++
		default:
			item.State = contract.DecisionHint
			evidenceItems = append(evidenceItems, item)
		}
	}
	return layers, assets, evidenceItems, nextLayer, nextAsset
}

func visionBBoxToRect(box visiondetector.BBox) geometry.Rect {
	return geometry.Rect{
		X:      int(math.Round(box.X)),
		Y:      int(math.Round(box.Y)),
		Width:  int(math.Round(box.Width)),
		Height: int(math.Round(box.Height)),
	}
}

func canEmitVisionImage(image contract.ImageMeta, candidate visiondetector.Candidate, box geometry.Rect, layers []contract.Layer) bool {
	if box.Empty() || candidate.Confidence < 0.50 {
		return false
	}
	imageArea := max(1, image.Width*image.Height)
	boxArea := box.Area()
	if boxArea < 12 {
		return false
	}
	if boxArea*100 >= imageArea*18 {
		return false
	}
	if box.Width*100 >= image.Width*72 || box.Height*100 >= image.Height*28 {
		return false
	}
	for _, layer := range layers {
		if !layer.Visible || layer.Kind != contract.LayerRaster {
			continue
		}
		if geometry.IoU(layer.BBox, box) >= 0.55 || geometry.IoA(box, layer.BBox) >= 0.82 {
			return false
		}
	}
	return true
}

func canEmitVisionBackground(candidate visiondetector.Candidate, box geometry.Rect, layers []contract.Layer) bool {
	if box.Empty() || candidate.Confidence < 0.45 {
		return false
	}
	if box.Area() < 200 {
		return false
	}
	return true
}

func suppressM29CoveredByVision(layers []contract.Layer, assets []contract.Asset) ([]contract.Layer, []contract.Asset) {
	visionBoxes := make([]geometry.Rect, 0)
	for _, layer := range layers {
		if !layer.Visible {
			continue
		}
		isVision := false
		for _, ref := range layer.SourceRefs {
			if ref.Kind == "vision_detector_candidate" {
				isVision = true
				break
			}
		}
		if isVision {
			visionBoxes = append(visionBoxes, layer.BBox)
		}
	}
	if len(visionBoxes) == 0 {
		return layers, assets
	}
	suppressedAssets := map[string]bool{}
	for i := range layers {
		if !layers[i].Visible {
			continue
		}
		isVision := false
		for _, ref := range layers[i].SourceRefs {
			if ref.Kind == "vision_detector_candidate" {
				isVision = true
				break
			}
		}
		if isVision {
			continue
		}
		if layers[i].Kind != contract.LayerShape && layers[i].Kind != contract.LayerRaster {
			continue
		}
		for _, vb := range visionBoxes {
			if geometry.IoA(layers[i].BBox, vb) >= 0.70 {
				layers[i].Visible = false
				layers[i].Decision.State = contract.DecisionSuppress
				layers[i].Decision.Reason += "+covered_by_vision_candidate"
				if layers[i].Raster != nil && layers[i].Raster.AssetID != "" {
					suppressedAssets[layers[i].Raster.AssetID] = true
				}
				break
			}
		}
	}
	if len(suppressedAssets) == 0 {
		return layers, assets
	}
	filtered := assets[:0]
	for _, asset := range assets {
		if !suppressedAssets[asset.ID] {
			filtered = append(filtered, asset)
		}
	}
	return layers, filtered
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

func estimateFontSize(bboxHeight, bboxWidth, charCount int) int {
	fromHeight := int(math.Round(float64(bboxHeight) / 1.25))
	if charCount > 0 && bboxWidth > 0 {
		maxFit := bboxWidth / charCount
		if maxFit < fromHeight {
			fromHeight = maxFit
		}
	}
	if fromHeight < 8 {
		return 8
	}
	if fromHeight > 120 {
		return 120
	}
	return fromHeight
}

func max(a, b int) int {
	if a > b {
		return a
	}
	return b
}

func abs(value int) int {
	if value < 0 {
		return -value
	}
	return value
}

func maxFloat(a, b float64) float64 {
	if a > b {
		return a
	}
	return b
}

func suppressDuplicateVisibleOwners(image contract.ImageMeta, layers []contract.Layer, assets []contract.Asset) ([]contract.Layer, []contract.Asset) {
	suppressedAssets := map[string]bool{}
	for i := range layers {
		if !layers[i].Visible || layers[i].Kind != contract.LayerRaster {
			continue
		}
		if !structuralRasterOwner(image, layers[i], layers) {
			continue
		}
		suppressLayer(&layers[i], "structural_raster_consumed_by_editable_children")
		if layers[i].Raster != nil && layers[i].Raster.AssetID != "" {
			suppressedAssets[layers[i].Raster.AssetID] = true
		}
	}

	for i := range layers {
		if !layers[i].Visible || layers[i].Kind != contract.LayerShape {
			continue
		}
		if raster := coveringVisibleRaster(layers[i], layers); raster != nil {
			suppressLayer(&layers[i], "shape_covered_by_raster_owner:"+raster.ID)
		}
	}

	for i := range layers {
		if !layers[i].Visible || layers[i].Kind != contract.LayerShape {
			continue
		}
		for j := i + 1; j < len(layers); j++ {
			if !layers[j].Visible || layers[j].Kind != contract.LayerShape {
				continue
			}
			if nearDuplicateShape(layers[i], layers[j]) {
				suppressLayer(&layers[j], "duplicate_shape_owner:"+layers[i].ID)
			}
		}
	}

	if len(suppressedAssets) == 0 {
		return layers, assets
	}
	filtered := assets[:0]
	for _, asset := range assets {
		if !suppressedAssets[asset.ID] {
			filtered = append(filtered, asset)
		}
	}
	return layers, filtered
}

func structuralRasterOwner(image contract.ImageMeta, layer contract.Layer, layers []contract.Layer) bool {
	imageArea := max(1, image.Width*image.Height)
	box := layer.BBox
	if geometry.IoA(imageBBox(image), box) >= 0.98 {
		return true
	}
	nearFullPage := box.Area()*100 >= imageArea*72 || (box.Width*100 >= image.Width*92 && box.Height*100 >= image.Height*50)
	if !nearFullPage {
		return false
	}
	contained := 0
	containedRaster := 0
	containedText := 0
	containedRasterArea := 0
	for _, child := range layers {
		if !child.Visible || child.ID == layer.ID {
			continue
		}
		if child.BBox.Area() <= 0 || child.BBox.Area()*100 >= box.Area()*92 {
			continue
		}
		if geometry.IoA(child.BBox, box) < 0.92 {
			continue
		}
		switch child.Kind {
		case contract.LayerRaster:
			contained++
			containedRaster++
			containedRasterArea += child.BBox.Area()
		case contract.LayerShape:
			contained++
		case contract.LayerText:
			contained++
			containedText++
		}
	}
	if contained >= 3 || containedRaster >= 2 || (containedText >= 2 && contained >= 2) {
		return true
	}
	return containedRaster >= 2 && containedRasterArea*100 >= box.Area()*24
}

func nearDuplicateShape(a, b contract.Layer) bool {
	if a.BBox.Area() <= 0 || b.BBox.Area() <= 0 {
		return false
	}
	if geometry.IoU(a.BBox, b.BBox) >= 0.88 {
		return true
	}
	overlap := maxFloat(geometry.IoA(a.BBox, b.BBox), geometry.IoA(b.BBox, a.BBox))
	if overlap < 0.96 {
		return false
	}
	areaDelta := abs(a.BBox.Area() - b.BBox.Area())
	return areaDelta*100 <= max(a.BBox.Area(), b.BBox.Area())*18
}

func coveringVisibleRaster(shape contract.Layer, layers []contract.Layer) *contract.Layer {
	for i := range layers {
		raster := &layers[i]
		if !raster.Visible || raster.Kind != contract.LayerRaster || raster.Z <= shape.Z {
			continue
		}
		if raster.BBox.Area() < shape.BBox.Area() {
			continue
		}
		if geometry.IoA(shape.BBox, raster.BBox) >= 0.98 {
			return raster
		}
	}
	return nil
}

func suppressLayer(layer *contract.Layer, reason string) {
	layer.Visible = false
	layer.GroupID = ""
	layer.Decision.State = contract.DecisionSuppress
	if layer.Decision.Reason == "" {
		layer.Decision.Reason = reason
	} else {
		layer.Decision.Reason += "+" + reason
	}
}

func buildMajorGroups(image contract.ImageMeta, layers []contract.Layer) []contract.Group {
	ownerIndexes := make([]int, 0, len(layers))
	imageArea := max(1, image.Width*image.Height)
	for i, layer := range layers {
		if !layer.Visible || !canOwnDraftGroup(layer) {
			continue
		}
		if layer.BBox.Area() < max(1800, imageArea/500) {
			continue
		}
		ownerIndexes = append(ownerIndexes, i)
	}
	sort.SliceStable(ownerIndexes, func(i, j int) bool {
		a, b := layers[ownerIndexes[i]], layers[ownerIndexes[j]]
		if a.BBox.Area() != b.BBox.Area() {
			return a.BBox.Area() < b.BBox.Area()
		}
		return a.ID < b.ID
	})

	assigned := map[string]bool{}
	var groups []contract.Group
	nextGroup := 1
	for _, ownerIndex := range ownerIndexes {
		owner := layers[ownerIndex]
		if assigned[owner.ID] {
			continue
		}
		childIDs := []string{owner.ID}
		for _, child := range layers {
			if !child.Visible || child.ID == owner.ID || assigned[child.ID] {
				continue
			}
			if child.BBox.Area() <= 0 || child.BBox.Area()*100 >= owner.BBox.Area()*94 {
				continue
			}
			if geometry.IoA(child.BBox, owner.BBox) < 0.92 {
				continue
			}
			childIDs = append(childIDs, child.ID)
		}
		if !acceptGroup(owner, childIDs, layers) {
			continue
		}
		groupID := fmt.Sprintf("group_%04d", nextGroup)
		nextGroup++
		for _, id := range childIDs {
			assigned[id] = true
		}
		groups = append(groups, contract.Group{
			ID:            groupID,
			Kind:          "major_region",
			BBox:          owner.BBox,
			SemanticTags:  groupTags(owner),
			ChildLayerIDs: childIDs,
			Decision: contract.Decision{
				State:         contract.DecisionEmit,
				BBoxAuthority: contract.BBoxAuthorityDerived,
				Reason:        "major_region_contains_editable_layers",
				SourceIDs:     sourceIDs(owner.SourceRefs),
			},
		})
	}
	return groups
}

func canOwnDraftGroup(layer contract.Layer) bool {
	return layer.Kind == contract.LayerShape || layer.Kind == contract.LayerRaster
}

func acceptGroup(owner contract.Layer, childIDs []string, layers []contract.Layer) bool {
	if len(childIDs) < 3 {
		return false
	}
	text := 0
	raster := 0
	shape := 0
	for _, id := range childIDs {
		layer := layerByID(layers, id)
		if layer == nil || layer.ID == owner.ID {
			continue
		}
		switch layer.Kind {
		case contract.LayerText:
			text++
		case contract.LayerRaster:
			raster++
		case contract.LayerShape:
			shape++
		}
	}
	return text+raster+shape >= 2 && (text > 0 || raster > 0)
}

func applyLayerGroups(layers []contract.Layer, groups []contract.Group) []contract.Layer {
	groupByLayer := map[string]string{}
	for _, group := range groups {
		for _, id := range group.ChildLayerIDs {
			groupByLayer[id] = group.ID
		}
	}
	for i := range layers {
		layers[i].GroupID = groupByLayer[layers[i].ID]
	}
	return layers
}

func layerByID(layers []contract.Layer, id string) *contract.Layer {
	for i := range layers {
		if layers[i].ID == id {
			return &layers[i]
		}
	}
	return nil
}

func groupTags(owner contract.Layer) []string {
	tags := []string{"editable_group"}
	switch owner.Kind {
	case contract.LayerRaster:
		tags = append(tags, "raster_backed_region")
	case contract.LayerShape:
		tags = append(tags, "shape_backed_region")
	}
	return tags
}

func sourceIDs(refs []contract.SourceRef) []string {
	var ids []string
	for _, ref := range refs {
		if ref.ID != "" {
			ids = append(ids, ref.ID)
		}
	}
	return ids
}
