package render

import (
	"fmt"
	"html"
	"image"
	"image/draw"
	"image/png"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/image/geometry"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/layoutir/contract"
)

const (
	PreviewHTMLFile       = "preview.html"
	DebugHTMLFile         = "preview_debug.html"
	PreviewReportFile     = "html_preview_report.md"
	PreviewAssetsDir      = "preview_assets"
	previewReportVersion  = "html_preview_report.v1"
	fullPageBackingReason = "full_page_backing_skipped"
)

type Options struct {
	OutputDir string
}

type Artifacts struct {
	PreviewHTML      string
	DebugHTML        string
	PreviewReport    string
	PreviewAssetsDir string
	AssetCount       int
	NodeCount        int
	EvidenceCount    int
	Warnings         []Warning
}

type Warning struct {
	Code    string
	Message string
	NodeID  string
}

type renderContext struct {
	doc              contract.Document
	nodes            []flatNode
	evidence         []contract.Evidence
	assetURLs        map[string]string
	evidenceAssetURL map[string]string
	warnings         []Warning
	assetCount       int
}

type flatNode struct {
	Node  contract.Node
	Depth int
}

func Write(doc contract.Document, options Options) (Artifacts, error) {
	if options.OutputDir == "" {
		return Artifacts{}, fmt.Errorf("output dir is required")
	}
	if err := os.MkdirAll(options.OutputDir, 0o755); err != nil {
		return Artifacts{}, err
	}
	ctx, err := newRenderContext(doc, options.OutputDir)
	if err != nil {
		return Artifacts{}, err
	}
	previewPath := filepath.Join(options.OutputDir, PreviewHTMLFile)
	debugPath := filepath.Join(options.OutputDir, DebugHTMLFile)
	reportPath := filepath.Join(options.OutputDir, PreviewReportFile)
	if err := os.WriteFile(previewPath, []byte(ctx.html(false)), 0o644); err != nil {
		return Artifacts{}, err
	}
	if err := os.WriteFile(debugPath, []byte(ctx.html(true)), 0o644); err != nil {
		return Artifacts{}, err
	}
	if err := os.WriteFile(reportPath, []byte(ctx.report()), 0o644); err != nil {
		return Artifacts{}, err
	}
	return Artifacts{
		PreviewHTML:      previewPath,
		DebugHTML:        debugPath,
		PreviewReport:    reportPath,
		PreviewAssetsDir: filepath.Join(options.OutputDir, PreviewAssetsDir),
		AssetCount:       ctx.assetCount,
		NodeCount:        len(ctx.nodes) + 1,
		EvidenceCount:    len(ctx.evidence),
		Warnings:         ctx.warnings,
	}, nil
}

func newRenderContext(doc contract.Document, outputDir string) (renderContext, error) {
	ctx := renderContext{
		doc:              doc,
		nodes:            flattenNodes(doc.Root),
		evidence:         append([]contract.Evidence(nil), doc.Evidence...),
		assetURLs:        map[string]string{},
		evidenceAssetURL: map[string]string{},
	}
	sort.SliceStable(ctx.evidence, func(i, j int) bool {
		a, b := ctx.evidence[i].BBox, ctx.evidence[j].BBox
		if zIndexForEvidence(ctx.evidence[i]) != zIndexForEvidence(ctx.evidence[j]) {
			return zIndexForEvidence(ctx.evidence[i]) < zIndexForEvidence(ctx.evidence[j])
		}
		if a.Y != b.Y {
			return a.Y < b.Y
		}
		if a.X != b.X {
			return a.X < b.X
		}
		return ctx.evidence[i].ID < ctx.evidence[j].ID
	})
	if err := ctx.prepareAssets(outputDir); err != nil {
		return renderContext{}, err
	}
	return ctx, nil
}

func flattenNodes(root contract.Node) []flatNode {
	var out []flatNode
	var walk func(contract.Node, int)
	walk = func(node contract.Node, depth int) {
		for _, child := range node.Children {
			out = append(out, flatNode{Node: child, Depth: depth + 1})
			walk(child, depth+1)
		}
	}
	walk(root, 0)
	sort.SliceStable(out, func(i, j int) bool {
		a, b := out[i].Node.BBox, out[j].Node.BBox
		if zIndexForNode(out[i].Node) != zIndexForNode(out[j].Node) {
			return zIndexForNode(out[i].Node) < zIndexForNode(out[j].Node)
		}
		if a.Y != b.Y {
			return a.Y < b.Y
		}
		if a.X != b.X {
			return a.X < b.X
		}
		return out[i].Node.ID < out[j].Node.ID
	})
	return out
}

func (ctx *renderContext) prepareAssets(outputDir string) error {
	source, sourceErr := decodeSource(ctx.doc.SourceImage.Path)
	assetsDir := filepath.Join(outputDir, PreviewAssetsDir)
	needAssets := len(ctx.doc.Assets) > 0 || hasCropEvidence(ctx.evidence)
	if needAssets {
		if err := os.MkdirAll(assetsDir, 0o755); err != nil {
			return err
		}
	}
	for _, asset := range ctx.doc.Assets {
		if asset.ID == "" {
			continue
		}
		if asset.URL != "" {
			ctx.assetURLs[asset.ID] = filepath.ToSlash(asset.URL)
			continue
		}
		if asset.Path != "" {
			ctx.assetURLs[asset.ID] = filepath.ToSlash(asset.Path)
			continue
		}
		if sourceErr != nil {
			ctx.warn("HTML_PREVIEW_ASSET_SOURCE_UNREADABLE", sourceErr.Error(), asset.ID)
			continue
		}
		path := filepath.Join(assetsDir, safeName(asset.ID)+".png")
		if err := writeCrop(path, source, asset.BBox); err != nil {
			ctx.warn("HTML_PREVIEW_ASSET_CROP_FAILED", err.Error(), asset.ID)
			continue
		}
		ctx.assetURLs[asset.ID] = filepath.ToSlash(filepath.Join(PreviewAssetsDir, filepath.Base(path)))
		ctx.assetCount++
	}
	for _, item := range ctx.evidence {
		if !cropEvidence(item) {
			continue
		}
		if fullPageBacking(ctx.doc.SourceImage, item.BBox) {
			ctx.warn("HTML_PREVIEW_EVIDENCE_CROP_SKIPPED", fullPageBackingReason, item.ID)
			continue
		}
		if sourceErr != nil {
			ctx.warn("HTML_PREVIEW_EVIDENCE_SOURCE_UNREADABLE", sourceErr.Error(), item.ID)
			continue
		}
		path := filepath.Join(assetsDir, safeName(item.ID)+".png")
		if err := writeCrop(path, source, item.BBox); err != nil {
			ctx.warn("HTML_PREVIEW_EVIDENCE_CROP_FAILED", err.Error(), item.ID)
			continue
		}
		ctx.evidenceAssetURL[item.ID] = filepath.ToSlash(filepath.Join(PreviewAssetsDir, filepath.Base(path)))
		ctx.assetCount++
	}
	return nil
}

func decodeSource(path string) (image.Image, error) {
	if strings.TrimSpace(path) == "" {
		return nil, fmt.Errorf("source image path is empty")
	}
	file, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer file.Close()
	img, err := png.Decode(file)
	if err != nil {
		return nil, err
	}
	return img, nil
}

func writeCrop(path string, src image.Image, box geometry.Rect) error {
	bounds := src.Bounds()
	clamped := geometry.Clamp(box, geometry.Rect{
		X:      bounds.Min.X,
		Y:      bounds.Min.Y,
		Width:  bounds.Dx(),
		Height: bounds.Dy(),
	})
	if clamped.Empty() {
		return fmt.Errorf("empty crop bbox %+v", box)
	}
	dst := image.NewRGBA(image.Rect(0, 0, clamped.Width, clamped.Height))
	draw.Draw(dst, dst.Bounds(), src, image.Point{X: clamped.X, Y: clamped.Y}, draw.Src)
	file, err := os.Create(path)
	if err != nil {
		return err
	}
	defer file.Close()
	return png.Encode(file, dst)
}

func (ctx *renderContext) html(debug bool) string {
	var b strings.Builder
	title := "Layout Preview"
	if debug {
		title = "Layout Debug Preview"
	}
	fmt.Fprintf(&b, "<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n")
	fmt.Fprintf(&b, "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n")
	fmt.Fprintf(&b, "<script>if(new URLSearchParams(location.search).has('capture'))document.documentElement.classList.add('capture-mode')</script>\n")
	fmt.Fprintf(&b, "<title>%s</title>\n<style>\n%s\n</style>\n</head>\n<body class=\"%s\">\n", title, css(), modeClass(debug))
	fmt.Fprintf(&b, "<main class=\"page\" style=\"width:%dpx;height:%dpx\" data-version=\"%s\">\n",
		ctx.doc.SourceImage.Width,
		ctx.doc.SourceImage.Height,
		html.EscapeString(ctx.doc.Version),
	)
	for _, item := range ctx.evidence {
		if !debug && !visibleEvidence(item) {
			continue
		}
		b.WriteString(ctx.renderEvidence(item, debug))
	}
	for _, item := range ctx.nodes {
		b.WriteString(ctx.renderNode(item, debug))
	}
	fmt.Fprintf(&b, "</main>\n</body>\n</html>\n")
	return b.String()
}

func (ctx *renderContext) renderNode(item flatNode, debug bool) string {
	node := item.Node
	var b strings.Builder
	classes := []string{"node", "node-" + string(node.Type)}
	if debug {
		classes = append(classes, "debug-outline")
	}
	style := boxStyle(node.BBox, zIndexForNode(node))
	fmt.Fprintf(&b, "<div class=\"%s\" style=\"%s\" data-node-id=\"%s\" data-node-type=\"%s\" data-depth=\"%d\" title=\"%s\">\n",
		strings.Join(classes, " "),
		style,
		html.EscapeString(node.ID),
		html.EscapeString(string(node.Type)),
		item.Depth,
		html.EscapeString(nodeTitle(node)),
	)
	switch {
	case node.Type == contract.NodeText && node.Text != nil:
		fmt.Fprintf(&b, "<span class=\"node-text-content\">%s</span>\n", html.EscapeString(node.Text.Characters))
	case requiresAsset(node.Type) && node.AssetRef != nil:
		if url := ctx.assetURLs[node.AssetRef.AssetID]; url != "" {
			fmt.Fprintf(&b, "<img class=\"node-image-content\" src=\"%s\" alt=\"%s\">\n", html.EscapeString(url), html.EscapeString(node.ID))
		}
	}
	if debug {
		fmt.Fprintf(&b, "<span class=\"label\">%s %s</span>\n", html.EscapeString(node.ID), html.EscapeString(string(node.Layout.Mode)))
	}
	fmt.Fprintf(&b, "</div>\n")
	return b.String()
}

func (ctx *renderContext) renderEvidence(item contract.Evidence, debug bool) string {
	var b strings.Builder
	role := item.RoleHint
	if role == "" {
		role = "none"
	}
	classes := []string{"evidence", "evidence-" + role}
	if debug {
		classes = append(classes, "debug-outline")
	}
	fmt.Fprintf(&b, "<div class=\"%s\" style=\"%s\" data-evidence-id=\"%s\" data-role=\"%s\" title=\"%s\">\n",
		strings.Join(classes, " "),
		boxStyle(item.BBox, zIndexForEvidence(item)),
		html.EscapeString(item.ID),
		html.EscapeString(role),
		html.EscapeString(evidenceTitle(item)),
	)
	if item.RoleHint == "text" {
		fmt.Fprintf(&b, "<span class=\"evidence-text-content\">%s</span>\n", html.EscapeString(item.Meta["text"]))
	} else if url := ctx.evidenceAssetURL[item.ID]; url != "" {
		fmt.Fprintf(&b, "<img class=\"evidence-image-content\" src=\"%s\" alt=\"%s\">\n", html.EscapeString(url), html.EscapeString(item.ID))
	}
	if debug {
		fmt.Fprintf(&b, "<span class=\"label\">%s %s</span>\n", html.EscapeString(item.ID), html.EscapeString(role))
	}
	fmt.Fprintf(&b, "</div>\n")
	return b.String()
}

func css() string {
	return `html,body{margin:0;padding:0;background:#1f2328;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#202124}
body{padding:24px}
.page{position:relative;overflow:hidden;background:#f7f7f7;box-shadow:0 16px 48px rgba(0,0,0,.32);transform-origin:top left}
.capture-mode body{padding:0;background:#fff}
.capture-mode .page{box-shadow:none}
.node,.evidence{position:absolute;box-sizing:border-box;left:var(--x);top:var(--y);width:var(--w);height:var(--h);z-index:var(--z);overflow:hidden}
.node-section{background:rgba(255,255,255,.02)}
.node-row{background:rgba(47,129,247,.035)}
.node-shape,.evidence-shape{background:rgba(238,238,238,.72)}
.node-text,.evidence-text{display:flex;align-items:center;color:#111;font-weight:500;line-height:1.05;white-space:nowrap;font-size:var(--font)}
.evidence-line{background:#222;min-height:1px}
.node-image-content,.evidence-image-content{display:block;width:100%;height:100%;object-fit:fill}
.node-icon .node-image-content,.evidence-icon .evidence-image-content{object-fit:contain}
.node-text-content,.evidence-text-content{display:block;overflow:hidden;text-overflow:ellipsis}
.debug .page{background:#fafafa}
.debug-outline{outline:1px solid rgba(27,31,36,.2)}
.debug .node-section{outline:2px solid rgba(255,149,0,.75);background:rgba(255,149,0,.04)}
.debug .node-row{outline:1px solid rgba(47,129,247,.85);background:rgba(47,129,247,.05)}
.debug .evidence-text{outline:1px solid rgba(51,153,85,.75)}
.debug .evidence-image,.debug .evidence-icon,.debug .evidence-texture_fragment,.debug .evidence-unknown{outline:1px solid rgba(191,80,191,.75)}
.debug .evidence-shape,.debug .evidence-line{outline:1px solid rgba(110,118,129,.7)}
.label{position:absolute;left:0;top:0;max-width:100%;padding:1px 3px;background:rgba(0,0,0,.68);color:#fff;font-size:9px;line-height:1.2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;pointer-events:none}
`
}

func (ctx *renderContext) report() string {
	var b strings.Builder
	fmt.Fprintf(&b, "# HTML Preview Report\n\n")
	fmt.Fprintf(&b, "- version: `%s`\n", previewReportVersion)
	fmt.Fprintf(&b, "- layout IR: `%s`\n", ctx.doc.Version)
	fmt.Fprintf(&b, "- source size: `%dx%d`\n", ctx.doc.SourceImage.Width, ctx.doc.SourceImage.Height)
	fmt.Fprintf(&b, "- nodes rendered: `%d`\n", len(ctx.nodes)+1)
	fmt.Fprintf(&b, "- evidence rendered: `%d`\n", len(ctx.evidence))
	fmt.Fprintf(&b, "- preview assets: `%d`\n", ctx.assetCount)
	fmt.Fprintf(&b, "- warnings: `%d`\n", len(ctx.warnings))
	fmt.Fprintf(&b, "\n## Policy\n\n")
	fmt.Fprintf(&b, "- renderer input is `ui_layout_ir.v1` only; it does not read M29/OCR/vision raw artifacts.\n")
	fmt.Fprintf(&b, "- source PNG is used only for local crop assets referenced by IR bboxes.\n")
	fmt.Fprintf(&b, "- text evidence is painted above image/shape evidence.\n")
	fmt.Fprintf(&b, "- full-page backing crops are skipped.\n")
	if len(ctx.warnings) > 0 {
		fmt.Fprintf(&b, "\n## Warnings\n\n")
		fmt.Fprintf(&b, "| code | node/evidence | message |\n")
		fmt.Fprintf(&b, "| --- | --- | --- |\n")
		for _, warning := range ctx.warnings {
			fmt.Fprintf(&b, "| `%s` | `%s` | %s |\n", warning.Code, warning.NodeID, escapeMarkdown(warning.Message))
		}
	}
	return b.String()
}

func boxStyle(box geometry.Rect, z int) string {
	return fmt.Sprintf("--x:%dpx;--y:%dpx;--w:%dpx;--h:%dpx;--z:%d;--font:%dpx", box.X, box.Y, box.Width, box.Height, z, fontSizeForBox(box))
}

func nodeTitle(node contract.Node) string {
	return fmt.Sprintf("%s %s %s %d,%d,%d,%d", node.ID, node.Type, node.Layout.Mode, node.BBox.X, node.BBox.Y, node.BBox.Width, node.BBox.Height)
}

func evidenceTitle(item contract.Evidence) string {
	return fmt.Sprintf("%s %s %s %d,%d,%d,%d", item.ID, item.Kind, item.RoleHint, item.BBox.X, item.BBox.Y, item.BBox.Width, item.BBox.Height)
}

func zIndexForNode(node contract.Node) int {
	switch node.Type {
	case contract.NodeSection:
		return 2
	case contract.NodeRow, contract.NodeColumn, contract.NodeGroup, contract.NodeOverlay:
		return 4
	case contract.NodeShape:
		return 12
	case contract.NodeImage, contract.NodeUnknownCrop:
		return 22
	case contract.NodeIcon:
		return 32
	case contract.NodeText:
		return 44
	default:
		return 8
	}
}

func zIndexForEvidence(item contract.Evidence) int {
	switch item.RoleHint {
	case "shape", "line":
		return 10
	case "image", "texture_fragment", "unknown":
		return 20
	case "icon":
		return 30
	case "text":
		return 40
	default:
		return 15
	}
}

func fontSizeForBox(box geometry.Rect) int {
	if box.Height <= 0 {
		return 12
	}
	return min(28, max(10, box.Height*72/100))
}

func visibleEvidence(item contract.Evidence) bool {
	switch item.RoleHint {
	case "text", "shape", "line", "image", "icon":
		return true
	default:
		return false
	}
}

func cropEvidence(item contract.Evidence) bool {
	switch item.RoleHint {
	case "image", "icon", "texture_fragment", "unknown":
		return true
	default:
		return false
	}
}

func hasCropEvidence(items []contract.Evidence) bool {
	for _, item := range items {
		if cropEvidence(item) {
			return true
		}
	}
	return false
}

func requiresAsset(value contract.NodeType) bool {
	return value == contract.NodeImage || value == contract.NodeIcon || value == contract.NodeUnknownCrop
}

func fullPageBacking(image contract.ImageMeta, box geometry.Rect) bool {
	if image.Width <= 0 || image.Height <= 0 || box.Empty() {
		return false
	}
	imageBox := geometry.Rect{Width: image.Width, Height: image.Height}
	if geometry.IoA(imageBox, box) >= 0.95 {
		return true
	}
	return float64(box.Area())/float64(image.Width*image.Height) >= 0.92
}

func (ctx *renderContext) warn(code string, message string, nodeID string) {
	ctx.warnings = append(ctx.warnings, Warning{
		Code:    code,
		Message: message,
		NodeID:  nodeID,
	})
}

func safeName(value string) string {
	var b strings.Builder
	for _, r := range value {
		if r >= 'a' && r <= 'z' || r >= 'A' && r <= 'Z' || r >= '0' && r <= '9' || r == '-' || r == '_' {
			b.WriteRune(r)
			continue
		}
		b.WriteByte('_')
	}
	out := strings.Trim(b.String(), "_")
	if out == "" {
		return "asset"
	}
	return out
}

func modeClass(debug bool) string {
	if debug {
		return "debug"
	}
	return "preview"
}

func escapeMarkdown(value string) string {
	value = strings.ReplaceAll(value, "|", "\\|")
	value = strings.ReplaceAll(value, "\n", " ")
	return value
}
