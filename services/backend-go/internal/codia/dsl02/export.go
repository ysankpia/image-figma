package dsl02

import (
	"fmt"
	"image"
	"image/color"
	"image/draw"
	"math"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/emitter"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/ir"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/imageio"
)

const (
	Version      = "0.2"
	Kind         = "codia_runtime"
	AssetDirName = "assets"
)

func Export(taskID string, doc emitter.Document) (Document, error) {
	return export(taskID, doc, nil)
}

type ExportAssetOptions struct {
	TaskID          string
	Document        emitter.Document
	SourceImagePath string
	OutputDir       string
}

func ExportWithAssets(options ExportAssetOptions) (Document, error) {
	if strings.TrimSpace(options.SourceImagePath) == "" || strings.TrimSpace(options.OutputDir) == "" {
		return export(options.TaskID, options.Document, nil)
	}
	src, err := imageio.ReadPNG(options.SourceImagePath)
	if err != nil {
		return Document{}, fmt.Errorf("read source image for runtime assets: %w", err)
	}
	ctx := &assetContext{
		taskID:    options.TaskID,
		src:       src,
		outputDir: filepath.Join(options.OutputDir, AssetDirName),
		used:      map[string]int{},
	}
	if err := os.MkdirAll(ctx.outputDir, 0o755); err != nil {
		return Document{}, fmt.Errorf("create runtime asset dir: %w", err)
	}
	return export(options.TaskID, options.Document, ctx)
}

func export(taskID string, doc emitter.Document, assets *assetContext) (Document, error) {
	if doc.SchemaName != emitter.SchemaName {
		return Document{}, fmt.Errorf("expected %s, got %q", emitter.SchemaName, doc.SchemaName)
	}
	root := convertNode(doc.Root, true, assets)
	if assets != nil && assets.err != nil {
		return Document{}, assets.err
	}
	if root.BBox.Width <= 0 || root.BBox.Height <= 0 {
		return Document{}, fmt.Errorf("root bbox has invalid size: %+v", root.BBox)
	}
	return Document{
		Version: Version,
		Kind:    Kind,
		TaskID:  taskID,
		Page: Page{
			Name:   "Codia Beta",
			Width:  root.BBox.Width,
			Height: root.BBox.Height,
			Background: Background{
				Type:  "color",
				Value: rootBackground(doc.Root),
			},
		},
		Assets: assetsList(assets),
		Root:   root,
		Meta: map[string]any{
			"source":           "go_codiacompile",
			"sourceSchemaName": doc.SchemaName,
			"sourceVersion":    doc.Version,
			"summary":          doc.Summary,
		},
	}, nil
}

type assetContext struct {
	taskID    string
	src       image.Image
	outputDir string
	assets    []Asset
	used      map[string]int
	err       error
}

func convertNode(node emitter.Node, isRoot bool, assets *assetContext) Node {
	role := runtimeRole(node.Role)
	if isRoot {
		role = "Root"
	}
	out := Node{
		ID:       firstNonEmpty(node.ID, node.SchemaID, "node"),
		SchemaID: node.SchemaID,
		Role:     role,
		Type:     runtimeType(node),
		Name:     firstNonEmpty(node.Name, fallbackName(role)),
		BBox:     runtimeBBox(node, isRoot),
		Style:    runtimeStyle(node, assets),
		Meta: map[string]any{
			"sourceRole":      string(node.Role),
			"sourceFigmaType": string(node.Type),
			"sourceBBox":      fromIRBBox(node.SourceBBox),
			"figmaBBox":       fromIRBBox(node.FigmaBBox),
			"seq":             node.Seq,
		},
	}
	if out.SchemaID != "" {
		out.Meta["schemaId"] = out.SchemaID
	}
	if out.Type == "text" {
		characters := ""
		if node.Text != nil {
			characters = node.Text.Characters
		}
		out.Text = &Text{Characters: characters}
	}
	if out.Type == "image" && node.Asset != nil {
		out.Meta["asset"] = *node.Asset
	}
	if out.Type == "image" && assets != nil {
		attachImageAsset(assets, &out, node)
	}
	for _, child := range node.Children {
		out.Children = append(out.Children, convertNode(child, false, assets))
	}
	if len(out.Style) == 0 {
		out.Style = nil
	}
	if len(out.Meta) == 0 {
		out.Meta = nil
	}
	return out
}

func attachImageAsset(ctx *assetContext, out *Node, node emitter.Node) {
	if ctx.err != nil || ctx.src == nil {
		return
	}
	crop, bbox, ok := cropFromSource(ctx.src, node.SourceBBox)
	if !ok {
		out.Meta["assetSkipped"] = "invalid_source_bbox"
		return
	}
	assetID := uniqueAssetID(ctx, firstNonEmpty(node.ID, node.SchemaID, fmt.Sprintf("seq_%04d", node.Seq)))
	fileName := assetID + ".png"
	if err := imageio.WritePNG(filepath.Join(ctx.outputDir, fileName), crop); err != nil {
		ctx.err = fmt.Errorf("write runtime image asset %s: %w", fileName, err)
		return
	}
	out.Image = &Image{
		AssetID: assetID,
		Mode:    "fill",
	}
	out.Meta["runtimeAssetId"] = assetID
	out.Meta["runtimeAssetBBox"] = bbox
	ctx.assets = append(ctx.assets, Asset{
		AssetID: assetID,
		Type:    "image",
		Role:    out.Role,
		URL:     filepath.ToSlash(filepath.Join(AssetDirName, fileName)),
		Format:  "png",
		Width:   bbox.Width,
		Height:  bbox.Height,
		Storage: "local",
		Meta: map[string]any{
			"nodeId":     out.ID,
			"schemaId":   out.SchemaID,
			"sourceBBox": bbox,
		},
	})
}

func cropFromSource(src image.Image, bbox ir.BBox) (image.Image, BBox, bool) {
	bounds := src.Bounds()
	width := bounds.Dx()
	height := bounds.Dy()
	if width <= 0 || height <= 0 || bbox.Width <= 0 || bbox.Height <= 0 {
		return nil, BBox{}, false
	}
	x1 := clampInt(bbox.X, 0, width)
	y1 := clampInt(bbox.Y, 0, height)
	x2 := clampInt(bbox.X+bbox.Width, x1+1, width)
	y2 := clampInt(bbox.Y+bbox.Height, y1+1, height)
	if x2 <= x1 || y2 <= y1 {
		return nil, BBox{}, false
	}
	rect := image.Rect(0, 0, x2-x1, y2-y1)
	out := image.NewRGBA(rect)
	draw.Draw(out, rect, src, image.Pt(bounds.Min.X+x1, bounds.Min.Y+y1), draw.Src)
	return out, BBox{X: x1, Y: y1, Width: x2 - x1, Height: y2 - y1}, true
}

func uniqueAssetID(ctx *assetContext, raw string) string {
	base := "asset_" + sanitizeID(raw)
	if base == "asset_" {
		base = "asset_image"
	}
	count := ctx.used[base]
	ctx.used[base] = count + 1
	if count == 0 {
		return base
	}
	return fmt.Sprintf("%s_%02d", base, count+1)
}

func sanitizeID(raw string) string {
	var b strings.Builder
	lastUnderscore := false
	for _, r := range strings.ToLower(strings.TrimSpace(raw)) {
		if (r >= 'a' && r <= 'z') || (r >= '0' && r <= '9') {
			b.WriteRune(r)
			lastUnderscore = false
			continue
		}
		if !lastUnderscore {
			b.WriteByte('_')
			lastUnderscore = true
		}
	}
	return strings.Trim(b.String(), "_")
}

func assetsList(ctx *assetContext) []Asset {
	if ctx == nil || len(ctx.assets) == 0 {
		return []Asset{}
	}
	return ctx.assets
}

func runtimeRole(role ir.Role) string {
	switch role {
	case ir.RoleRoot:
		return "Root"
	case ir.RoleViewGroup:
		return "ViewGroup"
	case ir.RoleListView:
		return "ListView"
	case ir.RoleActionBar:
		return "ActionBar"
	case ir.RoleStatusBar:
		return "StatusBar"
	case ir.RoleBottomNavigation:
		return "BottomNavigation"
	case ir.RoleButton:
		return "Button"
	case ir.RoleEditText:
		return "EditText"
	case ir.RoleTextView:
		return "TextView"
	case ir.RoleImageView:
		return "ImageView"
	case ir.RoleBackground:
		return "Background"
	case ir.RoleBgButton:
		return "bg_Button"
	case ir.RoleBgEditText:
		return "bg_EditText"
	default:
		return "ViewGroup"
	}
}

func runtimeType(node emitter.Node) string {
	switch node.Type {
	case ir.FigmaFrame:
		return "frame"
	case ir.FigmaText:
		return "text"
	case ir.FigmaRoundedRectangle:
		if node.Role == ir.RoleImageView {
			return "image"
		}
		return "shape"
	default:
		return "frame"
	}
}

func runtimeBBox(node emitter.Node, isRoot bool) BBox {
	if isRoot {
		return fromIRBBox(node.FigmaBBox)
	}
	return fromIRBBox(node.RelativeBBox)
}

func fromIRBBox(bbox ir.BBox) BBox {
	return BBox{
		X:      bbox.X,
		Y:      bbox.Y,
		Width:  maxInt(1, bbox.Width),
		Height: maxInt(1, bbox.Height),
	}
}

func runtimeStyle(node emitter.Node, assets *assetContext) map[string]any {
	style := map[string]any{}
	if node.Type == ir.FigmaFrame {
		style["clipContent"] = false
	}
	if node.Style.Visible {
		style["visible"] = true
	}
	if node.Style.Opacity > 0 {
		style["opacity"] = node.Style.Opacity
	}
	fill := firstSolidFill(node.Style.FillPaints)
	if fill != "" {
		if node.Type == ir.FigmaText {
			style["color"] = fill
		} else {
			style["fill"] = fill
		}
	}
	if node.Style.CornerRadius != nil {
		style["radius"] = runtimeRadius(*node.Style.CornerRadius)
	}
	if node.Style.Font != nil {
		if node.Style.Font.Family != "" {
			style["fontFamily"] = node.Style.Font.Family
		}
		if node.Style.Font.Size > 0 {
			style["fontSize"] = node.Style.Font.Size
		}
	}
	if node.Style.LineHeight != nil && node.Style.LineHeight.Value > 0 {
		style["lineHeight"] = node.Style.LineHeight.Value
	}
	if node.Type == ir.FigmaText {
		applyRuntimeTextFallbacks(style, node, assets)
	}
	return style
}

func applyRuntimeTextFallbacks(style map[string]any, node emitter.Node, assets *assetContext) {
	if _, ok := style["fontFamily"]; !ok {
		style["fontFamily"] = "Inter"
	}
	if _, ok := style["fontSize"]; !ok {
		style["fontSize"] = inferTextFontSize(node.SourceBBox.Height)
	}
	if _, ok := style["lineHeight"]; !ok {
		style["lineHeight"] = maxInt(1, node.SourceBBox.Height)
	}
	if _, ok := style["color"]; ok {
		return
	}
	if assets != nil && assets.src != nil {
		if color, ok := inferTextForegroundColor(assets.src, node.SourceBBox); ok {
			style["color"] = color
			return
		}
	}
	style["color"] = "#111827"
}

func inferTextFontSize(height int) int {
	if height <= 0 {
		return 14
	}
	return clampInt(int(math.Round(float64(height)*0.78)), 8, 72)
}

type colorBucket struct {
	count     int
	sumR      int
	sumG      int
	sumB      int
	avgR      int
	avgG      int
	avgB      int
	finalized bool
}

func inferTextForegroundColor(src image.Image, bbox ir.BBox) (string, bool) {
	bounds := src.Bounds()
	x1 := clampInt(bbox.X, 0, bounds.Dx())
	y1 := clampInt(bbox.Y, 0, bounds.Dy())
	x2 := clampInt(bbox.X+bbox.Width, x1, bounds.Dx())
	y2 := clampInt(bbox.Y+bbox.Height, y1, bounds.Dy())
	if x2 <= x1 || y2 <= y1 {
		return "", false
	}
	all := map[int]*colorBucket{}
	border := map[int]*colorBucket{}
	borderX := maxInt(1, (x2-x1)/6)
	borderY := maxInt(1, (y2-y1)/5)
	total := 0
	for y := y1; y < y2; y++ {
		for x := x1; x < x2; x++ {
			rgba := color.RGBAModel.Convert(src.At(bounds.Min.X+x, bounds.Min.Y+y)).(color.RGBA)
			if rgba.A < 32 {
				continue
			}
			addColorBucket(all, rgba)
			if x < x1+borderX || x >= x2-borderX || y < y1+borderY || y >= y2-borderY {
				addColorBucket(border, rgba)
			}
			total++
		}
	}
	if total == 0 {
		return "", false
	}
	background := dominantColorBucket(border)
	if background == nil {
		background = dominantColorBucket(all)
	}
	if background == nil {
		return "", false
	}
	finalizeColorBucket(background)
	candidates := make([]*colorBucket, 0, len(all))
	for _, bucket := range all {
		finalizeColorBucket(bucket)
		if bucket.count < maxInt(2, total/1200) {
			continue
		}
		if colorDistance(bucket, background) < 36 {
			continue
		}
		candidates = append(candidates, bucket)
	}
	if len(candidates) == 0 {
		if relativeLuminance(background) < 0.48 {
			return "#FFFFFF", true
		}
		return "#111827", true
	}
	sort.SliceStable(candidates, func(i, j int) bool {
		return foregroundScore(candidates[i], background) > foregroundScore(candidates[j], background)
	})
	winner := candidates[0]
	return fmt.Sprintf("#%02X%02X%02X", clampInt(winner.avgR, 0, 255), clampInt(winner.avgG, 0, 255), clampInt(winner.avgB, 0, 255)), true
}

func addColorBucket(buckets map[int]*colorBucket, rgba color.RGBA) {
	key := (int(rgba.R)/32)*64 + (int(rgba.G)/32)*8 + int(rgba.B)/32
	bucket := buckets[key]
	if bucket == nil {
		bucket = &colorBucket{}
		buckets[key] = bucket
	}
	bucket.count++
	bucket.sumR += int(rgba.R)
	bucket.sumG += int(rgba.G)
	bucket.sumB += int(rgba.B)
}

func dominantColorBucket(buckets map[int]*colorBucket) *colorBucket {
	var best *colorBucket
	for _, bucket := range buckets {
		if best == nil || bucket.count > best.count {
			best = bucket
		}
	}
	return best
}

func finalizeColorBucket(bucket *colorBucket) {
	if bucket == nil || bucket.finalized || bucket.count <= 0 {
		return
	}
	bucket.avgR = bucket.sumR / bucket.count
	bucket.avgG = bucket.sumG / bucket.count
	bucket.avgB = bucket.sumB / bucket.count
	bucket.finalized = true
}

func foregroundScore(candidate *colorBucket, background *colorBucket) float64 {
	return float64(colorDistance(candidate, background)) * math.Log(float64(candidate.count)+1)
}

func colorDistance(a *colorBucket, b *colorBucket) int {
	dr := a.avgR - b.avgR
	dg := a.avgG - b.avgG
	db := a.avgB - b.avgB
	return int(math.Round(math.Sqrt(float64(dr*dr + dg*dg + db*db))))
}

func relativeLuminance(bucket *colorBucket) float64 {
	return (0.2126*float64(bucket.avgR) + 0.7152*float64(bucket.avgG) + 0.0722*float64(bucket.avgB)) / 255.0
}

func runtimeRadius(radius ir.CornerRadius) any {
	if !radius.Independent && nearlyEqual(radius.TopLeft, radius.TopRight) && nearlyEqual(radius.TopLeft, radius.BottomRight) && nearlyEqual(radius.TopLeft, radius.BottomLeft) {
		return radius.TopLeft
	}
	return map[string]float64{
		"topLeft":     radius.TopLeft,
		"topRight":    radius.TopRight,
		"bottomRight": radius.BottomRight,
		"bottomLeft":  radius.BottomLeft,
	}
}

func firstSolidFill(paints []ir.Paint) string {
	for _, paint := range paints {
		if paint.Type == "SOLID" && paint.Color != nil {
			return colorToHex(*paint.Color)
		}
	}
	return ""
}

func colorToHex(color ir.Color) string {
	return fmt.Sprintf("#%02X%02X%02X", channel(color.R), channel(color.G), channel(color.B))
}

func channel(value float64) int {
	if value < 0 {
		return 0
	}
	if value > 1 {
		return 255
	}
	return int(math.Round(value * 255))
}

func rootBackground(root emitter.Node) string {
	if fill := firstSolidFill(root.Style.FillPaints); fill != "" {
		return fill
	}
	return "#FFFFFF"
}

func fallbackName(role string) string {
	switch role {
	case "Root":
		return "Root"
	case "ViewGroup", "ListView", "ActionBar", "StatusBar", "BottomNavigation":
		return "Groups"
	case "ImageView":
		return "Image"
	case "Background", "bg_Button", "bg_EditText":
		return "Background"
	case "TextView":
		return "Text"
	default:
		return role
	}
}

func firstNonEmpty(values ...string) string {
	for _, value := range values {
		if value != "" {
			return value
		}
	}
	return ""
}

func nearlyEqual(a, b float64) bool {
	return math.Abs(a-b) < 0.000001
}

func maxInt(a, b int) int {
	if a > b {
		return a
	}
	return b
}

func clampInt(value, low, high int) int {
	if value < low {
		return low
	}
	if value > high {
		return high
	}
	return value
}
