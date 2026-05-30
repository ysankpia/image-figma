package leaf

import (
	"encoding/json"
	"fmt"
	"os"
	"sort"
	"strconv"
	"strings"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/ir"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/contract"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/evidence"
)

const (
	ArtifactName = "codia_leaf_ir.v1.json"
)

type Options struct {
	TokenPath string
}

func Compile(options Options) (ir.Document, error) {
	if options.TokenPath == "" {
		return ir.Document{}, fmt.Errorf("missing token path")
	}
	source, err := readEvidenceTokens(options.TokenPath)
	if err != nil {
		return ir.Document{}, err
	}
	doc := fromEvidence(source, options.TokenPath)
	return doc, nil
}

func readEvidenceTokens(path string) (evidence.Document, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return evidence.Document{}, err
	}
	var doc evidence.Document
	if err := json.Unmarshal(data, &doc); err != nil {
		return evidence.Document{}, err
	}
	if doc.SchemaName != "M29EvidenceTokens" {
		return evidence.Document{}, fmt.Errorf("expected M29EvidenceTokens, got %q", doc.SchemaName)
	}
	return doc, nil
}

func fromEvidence(source evidence.Document, tokenPath string) ir.Document {
	nodes := leafNodes(source.Tokens)
	root := ir.Node{
		ID:          "root_0",
		Role:        ir.RoleRoot,
		SourceBBox:  ir.BBox{X: 0, Y: 0, Width: source.Source.ImageWidth, Height: source.Source.ImageHeight},
		FigmaBBox:   ir.BBox{X: 0, Y: 0, Width: source.Source.ImageWidth, Height: source.Source.ImageHeight},
		FigmaType:   ir.FigmaFrame,
		VisibleName: "Root",
		SchemaID:    "root_0",
		Seq:         0,
		HasSeq:      true,
		SourcePath:  "/",
		Evidence: []ir.Evidence{{
			Kind:       "m29_viewport",
			BBox:       ir.BBox{X: 0, Y: 0, Width: source.Source.ImageWidth, Height: source.Source.ImageHeight},
			Confidence: 1,
			SourceID:   source.Source.SourcePath,
		}},
		Style:    ir.Style{Visible: true, Opacity: 1},
		Children: nodes,
	}
	roleCounts := map[string]int{string(ir.RoleRoot): 1}
	typeCounts := map[string]int{string(ir.FigmaFrame): 1}
	for _, node := range nodes {
		roleCounts[string(node.Role)]++
		typeCounts[string(node.FigmaType)]++
	}
	return ir.Document{
		SchemaName: ir.SchemaName,
		Version:    ir.Version,
		Source: ir.Source{
			InputPath:       tokenPath,
			CanvasVersion:   0,
			DesignFrameName: "M29 evidence leaf candidates",
			RootPath:        "/",
		},
		Root: root,
		Summary: ir.Summary{
			NodeCount:       len(nodes) + 1,
			MaxDepth:        1,
			RoleCounts:      roleCounts,
			FigmaTypeCounts: typeCounts,
		},
	}
}

func leafNodes(tokens []evidence.Token) []ir.Node {
	var nodes []ir.Node
	index := 1
	for _, token := range tokens {
		role, ok := roleForToken(token, tokens)
		if !ok {
			continue
		}
		node := nodeFromToken(index, token, role)
		nodes = append(nodes, node)
		index++
	}
	sort.SliceStable(nodes, func(i, j int) bool {
		a, b := nodes[i].SourceBBox, nodes[j].SourceBBox
		if a.Y != b.Y {
			return a.Y < b.Y
		}
		if a.X != b.X {
			return a.X < b.X
		}
		return nodes[i].ID < nodes[j].ID
	})
	for i := range nodes {
		seq := i + 1
		nodes[i].Seq = seq
		nodes[i].HasSeq = true
		nodes[i].SchemaID = schemaID(nodes[i].Role, nodes[i].SourceBBox, seq)
	}
	return nodes
}

func roleForToken(token evidence.Token, tokens []evidence.Token) (ir.Role, bool) {
	switch token.TokenType {
	case "text_token":
		if token.Disposition != "main" {
			return "", false
		}
		return ir.RoleTextView, true
	case "raster_region_token", "symbol_cluster_token":
		if token.Disposition != "main" {
			return "", false
		}
		return ir.RoleImageView, true
	case "surface_region_token":
		if token.Disposition != "main" {
			return "", false
		}
		if lineLikeBackgroundToken(token) {
			return "", false
		}
		if surfaceTokenLooksLikeImageLeaf(token) {
			return ir.RoleImageView, true
		}
		return ir.RoleBackground, true
	case "layer_background_token":
		if token.Disposition != "main" {
			return "", false
		}
		if lineLikeBackgroundToken(token) {
			return "", false
		}
		return ir.RoleBackground, true
	case "unknown_token":
		if reviewTokenCanBeControlBackground(token, tokens) {
			return ir.RoleBackground, true
		}
		return "", false
	default:
		return "", false
	}
}

func lineLikeBackgroundToken(token evidence.Token) bool {
	box := token.BBox
	if box.Width <= 0 || box.Height <= 0 {
		return true
	}
	if box.Height <= 4 && box.Width >= 80 {
		return true
	}
	aspect := float64(maxInt(box.Width, box.Height)) / float64(maxInt(1, minInt(box.Width, box.Height)))
	return aspect >= 18 && minInt(box.Width, box.Height) <= 6
}

func surfaceTokenLooksLikeImageLeaf(token evidence.Token) bool {
	box := token.BBox
	if box.Width < 36 || box.Height < 32 || areaBBox(box) > 4200 {
		return false
	}
	if hasReason(token.CompileHints.Reasons, "control_surface_candidate") {
		return false
	}
	if token.Measurements.TextureScore < 0.42 {
		return false
	}
	if colorCount := token.Measurements.ColorCount; colorCount > 0 && colorCount < 48 {
		return false
	}
	return hasReason(token.CompileHints.Reasons, "ocr_anchored_low_texture_surface") ||
		hasReason(token.CompileHints.Reasons, "local_surface_color_region")
}

func nodeFromToken(index int, token evidence.Token, role ir.Role) ir.Node {
	box := bboxFromToken(token)
	node := ir.Node{
		ID:          fmt.Sprintf("leaf_%04d", index),
		Role:        role,
		SourceBBox:  box,
		FigmaBBox:   box,
		FigmaType:   figmaType(role),
		VisibleName: visibleName(role, token),
		SourceGUID:  token.ID,
		SourcePath:  token.ID,
		Evidence: []ir.Evidence{{
			Kind:       evidenceKind(role, token),
			BBox:       box,
			Confidence: token.CompileHints.Confidence,
			SourceID:   token.ID,
			Notes:      token.TokenType,
		}},
		Style: styleFromToken(role, token),
	}
	if role == ir.RoleTextView {
		node.Text = &ir.Text{Characters: token.Content.Text}
	}
	if role == ir.RoleImageView {
		node.Asset = &ir.Asset{Kind: "crop", Hash: token.ID}
	}
	return node
}

func bboxFromToken(token evidence.Token) ir.BBox {
	return ir.BBox{
		X:      token.BBox.X,
		Y:      token.BBox.Y,
		Width:  token.BBox.Width,
		Height: token.BBox.Height,
	}
}

func figmaType(role ir.Role) ir.FigmaType {
	switch role {
	case ir.RoleTextView:
		return ir.FigmaText
	case ir.RoleImageView, ir.RoleBackground:
		return ir.FigmaRoundedRectangle
	default:
		return ir.FigmaFrame
	}
}

func visibleName(role ir.Role, token evidence.Token) string {
	switch role {
	case ir.RoleTextView:
		return token.Content.Text
	case ir.RoleImageView:
		return "Image"
	case ir.RoleBackground:
		return "Background"
	default:
		return "Groups"
	}
}

func evidenceKind(role ir.Role, token evidence.Token) string {
	switch role {
	case ir.RoleTextView:
		return "ocr_text"
	case ir.RoleImageView:
		if token.TokenType == "surface_region_token" {
			return "image_surface_crop"
		}
		if token.TokenType == "symbol_cluster_token" {
			return "image_or_icon_crop"
		}
		return "image_crop"
	case ir.RoleBackground:
		if token.TokenType == "unknown_token" {
			return "control_background_candidate"
		}
		if hasReason(token.CompileHints.Reasons, "control_surface_candidate") {
			return "control_surface_background"
		}
		if token.Measurements.CornerRadiusEstimate > 0 {
			return "rounded_background"
		}
		return "solid_background"
	default:
		return "m29_token"
	}
}

func hasReason(reasons []string, reason string) bool {
	for _, item := range reasons {
		if item == reason {
			return true
		}
	}
	return false
}

func styleFromToken(role ir.Role, token evidence.Token) ir.Style {
	style := ir.Style{Visible: true, Opacity: 1}
	if role == ir.RoleBackground || role == ir.RoleImageView {
		paint := ir.Paint{Type: fillType(role, token)}
		if color := parseHexColor(token.Measurements.MeanColor); color != nil {
			paint.Color = color
		}
		style.FillPaints = []ir.Paint{paint}
	}
	if token.Measurements.CornerRadiusEstimate > 0 {
		radius := token.Measurements.CornerRadiusEstimate
		style.CornerRadius = &ir.CornerRadius{
			TopLeft:     radius,
			TopRight:    radius,
			BottomLeft:  radius,
			BottomRight: radius,
			Independent: false,
		}
	}
	return style
}

func fillType(role ir.Role, token evidence.Token) string {
	if role == ir.RoleImageView || token.TokenType == "raster_region_token" || token.TokenType == "symbol_cluster_token" {
		return "IMAGE"
	}
	return "SOLID"
}

func schemaID(role ir.Role, box ir.BBox, seq int) string {
	if role == ir.RoleRoot {
		return "root_0"
	}
	return fmt.Sprintf("%s_%d_%d_%d", role, box.X, box.Y, seq)
}

func reviewTokenCanBeControlBackground(token evidence.Token, tokens []evidence.Token) bool {
	if token.Disposition != "review" || token.TokenType != "unknown_token" {
		return false
	}
	box := token.BBox
	if box.Width < 40 || box.Height < 18 || box.Height > 80 {
		return false
	}
	if areaBBox(box) > 20000 {
		return false
	}
	textCount := 0
	iconCount := 0
	for _, candidate := range tokens {
		if candidate.Disposition != "main" {
			continue
		}
		if !centerInsideToken(box, candidate.BBox, 4) && intersectionRatioToken(candidate.BBox, box) < 0.45 {
			continue
		}
		switch candidate.TokenType {
		case "text_token":
			textCount++
		case "symbol_cluster_token", "raster_region_token":
			if areaBBox(candidate.BBox) <= areaBBox(box)/2 {
				iconCount++
			}
		}
	}
	return textCount > 0 || iconCount > 0
}

func centerInsideToken(parent, child contract.BBox, tolerance int) bool {
	cx := child.X + child.Width/2
	cy := child.Y + child.Height/2
	return parent.X-tolerance <= cx &&
		parent.Y-tolerance <= cy &&
		parent.X+parent.Width+tolerance >= cx &&
		parent.Y+parent.Height+tolerance >= cy
}

func intersectionRatioToken(a, b contract.BBox) float64 {
	intersection := intersectionAreaToken(a, b)
	if intersection <= 0 {
		return 0
	}
	return float64(intersection) / float64(maxInt(1, areaBBox(a)))
}

func intersectionAreaToken(a, b contract.BBox) int {
	x1 := maxInt(a.X, b.X)
	y1 := maxInt(a.Y, b.Y)
	x2 := minInt(a.X+a.Width, b.X+b.Width)
	y2 := minInt(a.Y+a.Height, b.Y+b.Height)
	if x2 <= x1 || y2 <= y1 {
		return 0
	}
	return (x2 - x1) * (y2 - y1)
}

func areaBBox(box contract.BBox) int {
	return maxInt(0, box.Width) * maxInt(0, box.Height)
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

func parseHexColor(value string) *ir.Color {
	value = strings.TrimPrefix(strings.TrimSpace(value), "#")
	if len(value) != 6 {
		return nil
	}
	raw, err := strconv.ParseUint(value, 16, 32)
	if err != nil {
		return nil
	}
	return &ir.Color{
		R: float64((raw>>16)&0xff) / 255,
		G: float64((raw>>8)&0xff) / 255,
		B: float64(raw&0xff) / 255,
		A: 1,
	}
}
