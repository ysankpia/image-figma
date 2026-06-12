package pencil

import (
	"encoding/json"
	"fmt"
	"image"
	"image/color"
	"image/draw"
	"image/png"
	"math"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"

	"github.com/luqing-studio/image-figma/services/pencil-go/internal/m29/contract"
)

var (
	cjkPattern          = regexp.MustCompile(`[\x{3400}-\x{9fff}]`)
	latinOrDigitPattern = regexp.MustCompile(`[A-Za-z0-9]`)
	wordPattern         = regexp.MustCompile(`[\w\x{3400}-\x{9fff}]`)
)

var CJKFontCandidates = []string{
	"Noto Sans SC",
	"PingFang SC",
	"Microsoft YaHei",
	"Source Han Sans SC",
	"Arial Unicode MS",
	"Arial",
}

var LatinFontCandidates = []string{
	"Inter",
	"SF Pro Text",
	"Segoe UI",
	"Helvetica Neue",
	"Arial",
}

type ExportOptions struct {
	InputDir           string
	OutputDir          string
	Name               string
	PageFill           string
	Mode               Mode
	IDPrefix           string
	AssetPageDir       string
	X                  int
	Y                  int
	DisableArtTextGate bool
}

type Result struct {
	Mode     Mode
	Document Document
	Manifest Manifest
	Summary  Summary
}

type primitive struct {
	ID            string
	PrimitiveType string
	BBox          contract.BBox
	CropRef       string
	MaskRef       string
	Text          string
}

type layer struct {
	ID                string
	SourcePrimitiveID string
	Role              string
	BBox              contract.BBox
	FillImage         string
	Z                 int
}

func ExportMode(options ExportOptions, evidence contract.Document, mode Mode) (Result, error) {
	policy, ok := PolicyForMode(mode)
	if !ok {
		return Result{}, fmt.Errorf("unsupported mode %q", mode)
	}
	options.Mode = mode
	if options.Name == "" {
		options.Name = "M29 Pencil Export"
	}
	if options.PageFill == "" {
		options.PageFill = firstNonEmpty(evidence.Diagnostics.BackgroundColor, "#FFFFFF")
	}
	if options.IDPrefix == "" {
		options.IDPrefix = strings.ReplaceAll(string(mode), "-", "_")
	}
	if options.AssetPageDir == "" {
		options.AssetPageDir = "page_0001"
	}

	primByID := loadPrimitives(evidence)
	layers := buildReplayLayers(evidence)

	var textLayers []layer
	var editableTextPrimitives []primitive
	var cropLayers []layer
	var textDecisions []TextDecision

	for _, item := range layers {
		prim, ok := primByID[item.SourcePrimitiveID]
		if item.Role != "text_region" {
			cropLayers = append(cropLayers, item)
			continue
		}
		if !ok || strings.TrimSpace(prim.Text) == "" {
			cropLayers = append(cropLayers, item)
			continue
		}
		artReason := ""
		if !options.DisableArtTextGate {
			artReason = artTextRejectionReason(prim)
		}
		if artReason != "" {
			cropLayers = append(cropLayers, makeTextCropLayer(item, prim, "art_text_region"))
			textDecisions = append(textDecisions, TextDecision{PrimitiveID: prim.ID, Text: prim.Text, Decision: "crop", Reason: artReason})
			continue
		}
		if policy.CropTextRegions {
			cropLayers = append(cropLayers, makeTextCropLayer(item, prim, "text_region"))
		}
		if policy.VisibleOCRText {
			textLayers = append(textLayers, item)
			editableTextPrimitives = append(editableTextPrimitives, prim)
		}
		decision := "crop"
		if policy.CropTextRegions && policy.VisibleOCRText {
			decision = "crop_and_visible_ocr"
		} else if policy.VisibleOCRText {
			decision = "editable_text"
		}
		reason := "visual_fidelity_text_crop"
		if policy.VisibleOCRText {
			reason = "normal_ocr_text"
		}
		textDecisions = append(textDecisions, TextDecision{PrimitiveID: prim.ID, Text: prim.Text, Decision: decision, Reason: reason})
	}

	var suppressed []SuppressedCrop
	if policy.CropDedupe {
		cropLayers, suppressed = dedupeComponentCropLayers(cropLayers, evidence.Image.Width, evidence.Image.Height)
	}

	modeDir := filepath.Join(options.OutputDir, policy.DirName)
	assetRoot := filepath.Join(modeDir, "assets", "visible", options.AssetPageDir)
	if err := os.MkdirAll(assetRoot, 0o755); err != nil {
		return Result{}, err
	}

	counts := map[string]int{}
	var children []Node
	var assets []Asset
	knockoutNodes := 0
	for _, item := range cropLayers {
		counts[item.Role]++
		assetURL, asset, err := copyCropAsset(options.InputDir, assetRoot, options.AssetPageDir, item, editableTextPrimitives, policy.TextKnockout)
		if err != nil {
			return Result{}, err
		}
		if asset.TextKnockout {
			knockoutNodes++
		}
		assets = append(assets, asset)
		children = append(children, makeImageNode(options, item, assetURL, asset))
	}

	textNodes := 0
	for _, item := range textLayers {
		prim := primByID[item.SourcePrimitiveID]
		counts[item.Role]++
		node, err := makeTextNode(options, item, prim)
		if err != nil {
			return Result{}, err
		}
		children = append(children, node)
		textNodes++
	}

	sort.SliceStable(children, func(i, j int) bool {
		return nodeZ(children[i]) < nodeZ(children[j])
	})

	pageID := prefixedID(options, "m29_pencil_page")
	document := Document{
		Version: PenVersion,
		Children: []Node{
			{
				"id":       pageID,
				"type":     "frame",
				"name":     options.Name,
				"x":        options.X,
				"y":        options.Y,
				"width":    evidence.Image.Width,
				"height":   evidence.Image.Height,
				"layout":   "none",
				"fill":     options.PageFill,
				"clip":     false,
				"metadata": map[string]any{"type": "m29_pencil_production_page", "source": "m29_physical_evidence", "exportMode": mode, "rawSourceVisible": false},
				"children": children,
			},
		},
	}

	artText := 0
	cropText := 0
	for _, decision := range textDecisions {
		if strings.HasPrefix(decision.Reason, "large_") {
			artText++
		}
		if (decision.Decision == "crop" || decision.Decision == "crop_and_visible_ocr") && !strings.HasPrefix(decision.Reason, "large_") {
			cropText++
		}
	}
	internalSuppressed := 0
	for _, item := range suppressed {
		if item.Reason == "internal_fragment_covered_by_component_crop" {
			internalSuppressed++
		}
	}
	manifest := Manifest{
		Schema:                       "m29.pencil.production_manifest.v1",
		Pen:                          "design.pen",
		Mode:                         mode,
		ModeDescription:              policy.Description,
		Canvas:                       Canvas{Width: evidence.Image.Width, Height: evidence.Image.Height, Fill: options.PageFill},
		CropPolicy:                   policy.CropPolicy,
		VisibleOCRText:               policy.VisibleOCRText,
		CropTextRegions:              policy.CropTextRegions,
		Counts:                       counts,
		TextNodes:                    textNodes,
		CropNodes:                    len(cropLayers),
		TextKnockoutCropNodes:        knockoutNodes,
		ArtTextCropNodes:             artText,
		CropTextNodes:                cropText,
		SuppressedDuplicateCropNodes: len(suppressed),
		SuppressedInternalCropNodes:  internalSuppressed,
		TextDecisions:                textDecisions,
		SuppressedCropLayers:         suppressed,
		Assets:                       assets,
		FontPolicy: FontPolicy{
			PenPreviewFontFamily: "system-ui",
			CJKOrMixedCandidates: CJKFontCandidates,
			LatinCandidates:      LatinFontCandidates,
			FigmaImportRule:      "Use metadata.fontCandidates with figma.listAvailableFontsAsync(), then figma.loadFontAsync().",
			TextGrowth:           "fixed-width-height",
			LineHeight:           1.0,
			VerticalAlign:        "middle",
		},
		ProductionGuarantees: Guarantees{},
	}
	manifest.ProductionGuarantees = Guarantees{
		ReferencesSourceImage:     false,
		ReferencesRawCrops:        false,
		ReferencesMasks:           false,
		ReferencesTextRegionCrops: false,
	}
	summary := Summary{
		TextNodes:                    textNodes,
		CropNodes:                    len(cropLayers),
		TextKnockoutCropNodes:        knockoutNodes,
		ArtTextCropNodes:             artText,
		CropTextNodes:                cropText,
		SuppressedDuplicateCropNodes: len(suppressed),
		SuppressedInternalCropNodes:  internalSuppressed,
		AssetCount:                   len(assets),
	}
	return Result{Mode: mode, Document: document, Manifest: manifest, Summary: summary}, nil
}

func WriteJSON(path string, value any) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	data, err := json.MarshalIndent(value, "", "  ")
	if err != nil {
		return err
	}
	data = append(data, '\n')
	return os.WriteFile(path, data, 0o644)
}

func loadPrimitives(evidence contract.Document) map[string]primitive {
	out := map[string]primitive{}
	for _, item := range evidence.Primitives {
		out[item.ID] = primitive{
			ID:            item.ID,
			PrimitiveType: item.PrimitiveType,
			BBox:          item.BBox,
			CropRef:       item.CropRef,
			MaskRef:       item.MaskRef,
			Text:          item.Source.Text,
		}
	}
	return out
}

func buildReplayLayers(evidence contract.Document) []layer {
	items := append([]contract.Primitive(nil), evidence.Primitives...)
	sort.SliceStable(items, func(i, j int) bool {
		a, b := items[i], items[j]
		if roleOrder(a.PrimitiveType) != roleOrder(b.PrimitiveType) {
			return roleOrder(a.PrimitiveType) < roleOrder(b.PrimitiveType)
		}
		if a.BBox.Y != b.BBox.Y {
			return a.BBox.Y < b.BBox.Y
		}
		if a.BBox.X != b.BBox.X {
			return a.BBox.X < b.BBox.X
		}
		return a.ID < b.ID
	})
	out := make([]layer, 0, len(items))
	for i, item := range items {
		out = append(out, layer{
			ID:                item.ID,
			SourcePrimitiveID: item.ID,
			Role:              item.PrimitiveType,
			BBox:              item.BBox,
			FillImage:         filepath.ToSlash(filepath.Join("assets", item.CropRef)),
			Z:                 i + 1,
		})
	}
	return out
}

func roleOrder(role string) int {
	switch role {
	case "image_region":
		return 0
	case "surface_region":
		return 1
	case "unknown_region":
		return 2
	case "rect":
		return 3
	case "symbol_region":
		return 4
	case "text_region":
		return 5
	default:
		return 9
	}
}

func makeTextCropLayer(item layer, prim primitive, role string) layer {
	item.Role = role
	item.SourcePrimitiveID = prim.ID
	item.FillImage = filepath.ToSlash(filepath.Join("assets", prim.CropRef))
	return item
}

func artTextRejectionReason(prim primitive) string {
	text := strings.TrimSpace(prim.Text)
	width := float64(prim.BBox.Width)
	height := float64(prim.BBox.Height)
	area := width * height
	aspect := width / math.Max(1, height)
	alnumLen := len(wordPattern.FindAllString(text, -1))
	if alnumLen <= 1 && area >= 12000 && aspect >= 0.45 && aspect <= 1.45 {
		return "large_single_glyph_art_text"
	}
	if alnumLen <= 2 && area >= 18000 && aspect >= 0.55 && aspect <= 1.75 {
		return "large_short_glyph_art_text"
	}
	if len([]rune(text)) <= 8 && area >= 45000 && height >= 84 {
		return "large_logo_or_display_art_text"
	}
	return ""
}

func copyCropAsset(inputDir, assetRoot, assetPageDir string, item layer, textPrims []primitive, knockout bool) (string, Asset, error) {
	sourceRel := strings.TrimPrefix(item.FillImage, "assets/")
	sourcePath := assetPath(inputDir, sourceRel)
	if sourcePath == "" {
		return "", Asset{}, fmt.Errorf("missing crop asset for %s: %s", item.SourcePrimitiveID, sourceRel)
	}
	outputName := item.SourcePrimitiveID + ".png"
	outputPath := filepath.Join(assetRoot, outputName)
	asset := Asset{
		PrimitiveID:        item.SourcePrimitiveID,
		Role:               item.Role,
		VisibleAssetSource: "raw_crop",
		SourceCropRef:      sourceRel,
	}
	if knockout {
		mask, ok := buildTextMaskForLayer(inputDir, item.BBox, textPrims)
		if ok {
			img, err := readPNG(sourcePath)
			if err != nil {
				return "", Asset{}, err
			}
			clean := eraseMaskedPixels(img, mask)
			outputName = item.SourcePrimitiveID + ".clean.png"
			outputPath = filepath.Join(assetRoot, outputName)
			if err := writePNG(outputPath, clean); err != nil {
				return "", Asset{}, err
			}
			asset.VisibleAssetSource = "text_knockout_crop"
			asset.TextKnockout = true
			asset.KnockoutPixelCount = countMask(mask)
			asset.URL = "./" + filepath.ToSlash(filepath.Join("assets/visible", assetPageDir, outputName))
			return asset.URL, asset, nil
		}
	}
	if err := copyFile(sourcePath, outputPath); err != nil {
		return "", Asset{}, err
	}
	asset.URL = "./" + filepath.ToSlash(filepath.Join("assets/visible", assetPageDir, outputName))
	return asset.URL, asset, nil
}

func assetPath(inputDir, ref string) string {
	candidates := []string{
		filepath.Join(inputDir, "assets", ref),
		filepath.Join(inputDir, ref),
	}
	for _, candidate := range candidates {
		if _, err := os.Stat(candidate); err == nil {
			return candidate
		}
	}
	return ""
}

func makeImageNode(options ExportOptions, item layer, assetURL string, asset Asset) Node {
	b := item.BBox
	metadata := map[string]any{
		"type":          "m29_visible_crop",
		"primitiveId":   item.SourcePrimitiveID,
		"primitiveType": item.Role,
		"editableMode":  "raster_crop",
		"z":             item.Z,
	}
	metadata["visibleAssetSource"] = asset.VisibleAssetSource
	metadata["sourceCropRef"] = asset.SourceCropRef
	if asset.TextKnockout {
		metadata["textKnockout"] = true
		metadata["knockoutPixelCount"] = asset.KnockoutPixelCount
	}
	return Node{
		"id":       prefixedID(options, "node_"+item.ID),
		"type":     "rectangle",
		"name":     item.ID + " " + item.Role,
		"x":        b.X,
		"y":        b.Y,
		"width":    b.Width,
		"height":   b.Height,
		"fill":     map[string]any{"type": "image", "url": assetURL, "mode": "stretch"},
		"metadata": metadata,
	}
}

func makeTextNode(options ExportOptions, item layer, prim primitive) (Node, error) {
	text := strings.TrimSpace(prim.Text)
	candidates := fontCandidatesForText(text)
	measureFamily := localMeasureFamilyForText(text)
	fontSize := fitFontSize(text, prim.BBox)
	colorHex, colorSource, colorScore := sampleTextColor(assetPath(options.InputDir, prim.CropRef))
	fontWeight := inferFontWeight(text, prim.BBox)
	script := "latin"
	if hasCJK(text) && hasLatinOrDigit(text) {
		script = "mixed"
	} else if hasCJK(text) {
		script = "cjk"
	}
	b := item.BBox
	return Node{
		"id":                prefixedID(options, "text_"+prim.ID),
		"type":              "text",
		"name":              prim.ID + " editable text",
		"x":                 b.X,
		"y":                 b.Y,
		"width":             b.Width,
		"height":            b.Height,
		"content":           text,
		"textGrowth":        "fixed-width-height",
		"fontFamily":        "system-ui",
		"fontSize":          fontSize,
		"fontWeight":        fontWeight,
		"lineHeight":        1.0,
		"letterSpacing":     0,
		"textAlign":         "left",
		"textAlignVertical": "middle",
		"fill":              colorHex,
		"metadata": map[string]any{
			"type":                     "m29_editable_text",
			"primitiveId":              prim.ID,
			"primitiveType":            "text_region",
			"sourceText":               text,
			"editableMode":             "ocr_text",
			"script":                   script,
			"fontCandidates":           candidates,
			"figmaPreferredFontFamily": candidates[0],
			"fontFamilyPreview":        "system-ui",
			"measurementFontFamily":    measureFamily,
			"fontSize":                 fontSize,
			"fontWeight":               fontWeight,
			"colorSource":              colorSource,
			"colorScore":               math.Round(colorScore*10000) / 10000,
			"z":                        item.Z,
		},
	}, nil
}

func prefixedID(options ExportOptions, id string) string {
	prefix := strings.Trim(options.IDPrefix, "_")
	if prefix == "" {
		return id
	}
	return prefix + "__" + id
}

func nodeZ(node Node) int {
	meta, _ := node["metadata"].(map[string]any)
	switch value := meta["z"].(type) {
	case int:
		return value
	case float64:
		return int(value)
	default:
		return 0
	}
}

func firstNonEmpty(values ...string) string {
	for _, value := range values {
		if strings.TrimSpace(value) != "" {
			return value
		}
	}
	return ""
}

func hasCJK(text string) bool { return cjkPattern.MatchString(text) }

func hasLatinOrDigit(text string) bool { return latinOrDigitPattern.MatchString(text) }

func fontCandidatesForText(text string) []string {
	if hasCJK(text) {
		return CJKFontCandidates
	}
	return LatinFontCandidates
}

func localMeasureFamilyForText(text string) string {
	if hasCJK(text) {
		return "PingFang SC"
	}
	return "Helvetica Neue"
}

func textVisualUnits(text string) float64 {
	units := 0.0
	for _, ch := range text {
		switch {
		case ch == ' ' || ch == '\t':
			units += 0.32
		case cjkPattern.MatchString(string(ch)):
			units += 1.0
		case ch >= '0' && ch <= '9':
			units += 0.55
		case ch >= 'a' && ch <= 'z':
			units += 0.58
		case ch >= 'A' && ch <= 'Z':
			units += 0.66
		case strings.ContainsRune("+-/|:.，。、“”《》：；（）()[]{}", ch):
			units += 0.35
		default:
			units += 0.5
		}
	}
	return math.Max(1, units)
}

func fitFontSize(text string, bbox contract.BBox) float64 {
	if strings.TrimSpace(text) == "" {
		return math.Round(math.Max(8, math.Min(16, float64(bbox.Height)*0.72))*100) / 100
	}
	maxW := math.Max(1, float64(bbox.Width)*0.96)
	maxH := math.Max(1, float64(bbox.Height)*0.82)
	upper := int(clamp(float64(bbox.Height)*0.92, 8, 96))
	best := 6
	for size := 6; size <= upper; size++ {
		heuristicW := textVisualUnits(text) * float64(size)
		heuristicH := float64(size) * 0.92
		if heuristicW <= maxW && heuristicH <= maxH {
			best = size
		}
	}
	return float64(best)
}

func inferFontWeight(text string, bbox contract.BBox) string {
	if bbox.Height >= 56 {
		return "600"
	}
	if bbox.Height >= 34 || len([]rune(strings.TrimSpace(text))) <= 3 {
		return "500"
	}
	return "400"
}

func clamp(value, lo, hi float64) float64 {
	return math.Max(lo, math.Min(hi, value))
}

func sampleTextColor(path string) (string, string, float64) {
	if path == "" {
		return "#111111", "missing_crop_fallback", 0
	}
	img, err := readPNG(path)
	if err != nil {
		return "#111111", "missing_crop_fallback", 0
	}
	bounds := img.Bounds()
	if bounds.Dx() <= 0 || bounds.Dy() <= 0 {
		return "#111111", "empty_crop_fallback", 0
	}
	buckets := map[[3]uint8]int{}
	for y := bounds.Min.Y; y < bounds.Max.Y; y++ {
		for x := bounds.Min.X; x < bounds.Max.X; x++ {
			r, g, b, _ := img.At(x, y).RGBA()
			key := [3]uint8{uint8(r>>8)/16*16 + 8, uint8(g>>8)/16*16 + 8, uint8(b>>8)/16*16 + 8}
			buckets[key]++
		}
	}
	if len(buckets) == 0 {
		return "#111111", "empty_quant_fallback", 0
	}
	background := estimateEdgeBackground(img)
	total := bounds.Dx() * bounds.Dy()
	var bestColor [3]uint8
	bestScore := 0.0
	for key, count := range buckets {
		share := float64(count) / float64(total)
		if share < 0.006 || share > 0.72 {
			continue
		}
		rgb := [3]uint8{key[0], key[1], key[2]}
		delta := contrast(rgb, background)
		if delta < 0.14 {
			continue
		}
		areaReward := math.Sqrt(math.Min(0.18, share))
		polarityBonus := 1.0
		lum := luminance(rgb)
		if lum >= 0.88 || lum <= 0.18 {
			polarityBonus = 1.15
		}
		score := delta * areaReward * polarityBonus
		if score > bestScore {
			bestScore = score
			bestColor = rgb
		}
	}
	if bestScore > 0 {
		return rgbHex(bestColor), "edge_contrast_foreground_bucket", bestScore
	}
	fallback := [3]uint8{20, 24, 31}
	if luminance(background) < 0.48 {
		fallback = [3]uint8{255, 255, 255}
	}
	return rgbHex(fallback), "contrast_fallback", contrast(fallback, background)
}

func estimateEdgeBackground(img image.Image) [3]uint8 {
	b := img.Bounds()
	border := maxInt(1, minInt(4, minInt(b.Dx()/4, b.Dy()/4)))
	buckets := map[[3]uint8]int{}
	add := func(x, y int) {
		r, g, bb, _ := img.At(x, y).RGBA()
		key := [3]uint8{uint8(r>>8)/16*16 + 8, uint8(g>>8)/16*16 + 8, uint8(bb>>8)/16*16 + 8}
		buckets[key]++
	}
	for y := b.Min.Y; y < b.Max.Y; y++ {
		for x := b.Min.X; x < b.Max.X; x++ {
			if x < b.Min.X+border || x >= b.Max.X-border || y < b.Min.Y+border || y >= b.Max.Y-border {
				add(x, y)
			}
		}
	}
	var best [3]uint8
	bestCount := -1
	for key, count := range buckets {
		if count > bestCount {
			best = key
			bestCount = count
		}
	}
	if bestCount < 0 {
		return [3]uint8{255, 255, 255}
	}
	return best
}

func luminance(rgb [3]uint8) float64 {
	return 0.2126*float64(rgb[0])/255.0 + 0.7152*float64(rgb[1])/255.0 + 0.0722*float64(rgb[2])/255.0
}

func contrast(a, b [3]uint8) float64 {
	return math.Abs(luminance(a) - luminance(b))
}

func rgbHex(rgb [3]uint8) string {
	return fmt.Sprintf("#%02X%02X%02X", rgb[0], rgb[1], rgb[2])
}

func readPNG(path string) (image.Image, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	return png.Decode(f)
}

func writePNG(path string, img image.Image) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	f, err := os.Create(path)
	if err != nil {
		return err
	}
	defer f.Close()
	return png.Encode(f, img)
}

func copyFile(src, dst string) error {
	img, err := readPNG(src)
	if err != nil {
		return err
	}
	return writePNG(dst, img)
}

func buildTextMaskForLayer(inputDir string, layerBox contract.BBox, textPrims []primitive) ([][]bool, bool) {
	if layerBox.Width <= 0 || layerBox.Height <= 0 {
		return nil, false
	}
	mask := make([][]bool, layerBox.Height)
	for i := range mask {
		mask[i] = make([]bool, layerBox.Width)
	}
	any := false
	for _, textPrim := range textPrims {
		inter, ok := intersection(layerBox, textPrim.BBox)
		if !ok || textPrim.MaskRef == "" {
			continue
		}
		maskPath := assetPath(inputDir, textPrim.MaskRef)
		if maskPath == "" {
			continue
		}
		fullMask, err := readPNG(maskPath)
		if err != nil {
			continue
		}
		for y := 0; y < inter.Height; y++ {
			for x := 0; x < inter.Width; x++ {
				r, _, _, _ := fullMask.At(inter.X+x, inter.Y+y).RGBA()
				if r > 0 {
					lx := inter.X - layerBox.X + x
					ly := inter.Y - layerBox.Y + y
					if lx >= 0 && ly >= 0 && lx < layerBox.Width && ly < layerBox.Height {
						mask[ly][lx] = true
						any = true
					}
				}
			}
		}
	}
	if !any {
		return nil, false
	}
	return dilateMask(mask), true
}

func eraseMaskedPixels(img image.Image, mask [][]bool) image.Image {
	b := img.Bounds()
	dst := image.NewRGBA(image.Rect(0, 0, b.Dx(), b.Dy()))
	draw.Draw(dst, dst.Bounds(), img, b.Min, draw.Src)
	for y := 0; y < len(mask) && y < dst.Bounds().Dy(); y++ {
		for x := 0; x < len(mask[y]) && x < dst.Bounds().Dx(); x++ {
			if !mask[y][x] {
				continue
			}
			sumR, sumG, sumB, count := 0, 0, 0, 0
			for dy := -1; dy <= 1; dy++ {
				for dx := -1; dx <= 1; dx++ {
					if dx == 0 && dy == 0 {
						continue
					}
					nx, ny := x+dx, y+dy
					if ny >= 0 && ny < len(mask) && nx >= 0 && nx < len(mask[ny]) && !mask[ny][nx] {
						r, g, bb, _ := dst.At(nx, ny).RGBA()
						sumR += int(r >> 8)
						sumG += int(g >> 8)
						sumB += int(bb >> 8)
						count++
					}
				}
			}
			if count == 0 {
				continue
			}
			dst.Set(x, y, color.RGBA{R: uint8(sumR / count), G: uint8(sumG / count), B: uint8(sumB / count), A: 255})
		}
	}
	return dst
}

func dilateMask(mask [][]bool) [][]bool {
	out := make([][]bool, len(mask))
	for y := range mask {
		out[y] = make([]bool, len(mask[y]))
	}
	for y := range mask {
		for x := range mask[y] {
			if !mask[y][x] {
				continue
			}
			for dy := -1; dy <= 1; dy++ {
				for dx := -1; dx <= 1; dx++ {
					ny, nx := y+dy, x+dx
					if ny >= 0 && ny < len(mask) && nx >= 0 && nx < len(mask[ny]) {
						out[ny][nx] = true
					}
				}
			}
		}
	}
	return out
}

func countMask(mask [][]bool) int {
	count := 0
	for _, row := range mask {
		for _, value := range row {
			if value {
				count++
			}
		}
	}
	return count
}

func intersection(a, b contract.BBox) (contract.BBox, bool) {
	x1 := maxInt(a.X, b.X)
	y1 := maxInt(a.Y, b.Y)
	x2 := minInt(a.X+a.Width, b.X+b.Width)
	y2 := minInt(a.Y+a.Height, b.Y+b.Height)
	if x2 <= x1 || y2 <= y1 {
		return contract.BBox{}, false
	}
	return contract.BBox{X: x1, Y: y1, Width: x2 - x1, Height: y2 - y1}, true
}

func area(box contract.BBox) float64 {
	return math.Max(0, float64(box.Width)) * math.Max(0, float64(box.Height))
}

func intersectionArea(a, b contract.BBox) float64 {
	inter, ok := intersection(a, b)
	if !ok {
		return 0
	}
	return area(inter)
}

func ioa(a, b contract.BBox) float64 {
	aa := area(a)
	if aa <= 0 {
		return 0
	}
	return intersectionArea(a, b) / aa
}

func iou(a, b contract.BBox) float64 {
	inter := intersectionArea(a, b)
	if inter <= 0 {
		return 0
	}
	union := area(a) + area(b) - inter
	if union <= 0 {
		return 0
	}
	return inter / union
}

func dedupeComponentCropLayers(layers []layer, canvasW, canvasH int) ([]layer, []SuppressedCrop) {
	valid := make([]layer, 0, len(layers))
	for _, item := range layers {
		if area(item.BBox) > 0 {
			valid = append(valid, item)
		}
	}
	suppressedBy := map[string]struct {
		parent string
		reason string
	}{}
	for _, child := range sortedByArea(valid) {
		if parent, reason, ok := findComponentCropOwner(child, valid, canvasW, canvasH); ok {
			suppressedBy[child.ID] = struct {
				parent string
				reason string
			}{parent: parent.ID, reason: reason}
		}
	}
	byID := map[string]layer{}
	for _, item := range valid {
		byID[item.ID] = item
	}
	var suppressed []SuppressedCrop
	for id, owner := range suppressedBy {
		child := byID[id]
		rootID := owner.parent
		rootReason := owner.reason
		seen := map[string]bool{}
		for {
			next, ok := suppressedBy[rootID]
			if !ok || seen[rootID] {
				break
			}
			seen[rootID] = true
			rootID = next.parent
			rootReason = next.reason
		}
		root := byID[rootID]
		suppressed = append(suppressed, SuppressedCrop{
			ID:              child.ID,
			PrimitiveID:     child.SourcePrimitiveID,
			Role:            child.Role,
			Reason:          owner.reason,
			DuplicateOf:     rootID,
			DuplicateOfRole: root.Role,
			RootReason:      rootReason,
			IOAToOwner:      math.Round(ioa(child.BBox, root.BBox)*10000) / 10000,
		})
	}
	kept := make([]layer, 0, len(valid))
	for _, item := range valid {
		if _, ok := suppressedBy[item.ID]; !ok {
			kept = append(kept, item)
		}
	}
	sort.SliceStable(kept, func(i, j int) bool { return kept[i].Z < kept[j].Z })
	sort.SliceStable(suppressed, func(i, j int) bool { return suppressed[i].ID < suppressed[j].ID })
	return kept, suppressed
}

func sortedByArea(items []layer) []layer {
	out := append([]layer(nil), items...)
	sort.SliceStable(out, func(i, j int) bool {
		if area(out[i].BBox) != area(out[j].BBox) {
			return area(out[i].BBox) < area(out[j].BBox)
		}
		return out[i].ID < out[j].ID
	})
	return out
}

func findComponentCropOwner(child layer, layers []layer, canvasW, canvasH int) (layer, string, bool) {
	var same []layer
	var enclosing []layer
	for _, candidate := range layers {
		if candidate.ID == child.ID {
			continue
		}
		if iou(child.BBox, candidate.BBox) >= 0.92 && cropOwnerScore(candidate) > cropOwnerScore(child) {
			same = append(same, candidate)
			continue
		}
		if area(candidate.BBox) > area(child.BBox) && canComponentParent(candidate, child, canvasW, canvasH) {
			enclosing = append(enclosing, candidate)
		}
	}
	if len(same) > 0 {
		sort.SliceStable(same, func(i, j int) bool { return cropOwnerScore(same[i]) > cropOwnerScore(same[j]) })
		return same[0], "same_region_duplicate", true
	}
	if len(enclosing) > 0 {
		sort.SliceStable(enclosing, func(i, j int) bool {
			if area(enclosing[i].BBox) != area(enclosing[j].BBox) {
				return area(enclosing[i].BBox) < area(enclosing[j].BBox)
			}
			return cropOwnerPriority(enclosing[i]) > cropOwnerPriority(enclosing[j])
		})
		return enclosing[0], "internal_fragment_covered_by_component_crop", true
	}
	return layer{}, "", false
}

func cropOwnerPriority(item layer) int {
	switch item.Role {
	case "image_region":
		return 60
	case "surface_region":
		return 50
	case "unknown_region":
		return 45
	case "art_text_region":
		return 40
	case "symbol_region":
		return 30
	case "rect":
		return 10
	default:
		return 20
	}
}

func cropOwnerScore(item layer) int64 {
	return int64(cropOwnerPriority(item))*1_000_000_000 + int64(area(item.BBox))*1000 + int64(item.Z)
}

func canComponentParent(parent, child layer, canvasW, canvasH int) bool {
	if parent.Role == "rect" || isCanvasLikeCrop(parent, canvasW, canvasH) {
		return false
	}
	parentArea := area(parent.BBox)
	childArea := area(child.BBox)
	if parentArea <= 0 || childArea <= 0 {
		return false
	}
	minRatio := 1.12
	if parent.Role == "image_region" {
		minRatio = 1.03
	}
	if parentArea < childArea*minRatio {
		return false
	}
	canvasArea := float64(maxInt(1, canvasW) * maxInt(1, canvasH))
	limit := canvasArea * 0.12
	switch parent.Role {
	case "image_region":
		limit = canvasArea * 0.55
	case "surface_region", "unknown_region":
		limit = canvasArea * 0.32
	case "art_text_region":
		limit = canvasArea * 0.24
	case "symbol_region":
		limit = canvasArea * 0.18
	}
	if parentArea > limit {
		return false
	}
	if ioa(child.BBox, parent.BBox) < 0.9 {
		return false
	}
	if parent.Role == "image_region" {
		return true
	}
	margins := []float64{
		float64(child.BBox.X - parent.BBox.X),
		float64(child.BBox.Y - parent.BBox.Y),
		float64(parent.BBox.X + parent.BBox.Width - child.BBox.X - child.BBox.Width),
		float64(parent.BBox.Y + parent.BBox.Height - child.BBox.Y - child.BBox.Height),
	}
	strong := 0
	for _, margin := range margins {
		if margin >= 3 {
			strong++
		}
	}
	return strong >= 2
}

func isCanvasLikeCrop(item layer, canvasW, canvasH int) bool {
	if float64(item.BBox.Width) >= float64(canvasW)*0.96 && float64(item.BBox.Height) >= float64(canvasH)*0.82 {
		return true
	}
	return item.Role == "rect" && area(item.BBox) >= float64(canvasW*canvasH)*0.35
}

func minInt(a, b int) int {
	if a < b {
		return a
	}
	return b
}

func maxInt(a, b int) int {
	if a > b {
		return a
	}
	return b
}
