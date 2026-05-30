package canvasexport

import (
	"fmt"
	"path/filepath"
	"strings"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/canvas"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/ir"
)

const (
	canvasVersion   = 101
	schemaPluginID  = "1329812760871373657"
	schemaPluginKey = "schema:id"
)

func Export(doc ir.Document) (Result, error) {
	if doc.SchemaName != ir.SchemaName {
		return Result{}, fmt.Errorf("expected %s, got %q", ir.SchemaName, doc.SchemaName)
	}
	localID := 1
	designName := designFrameName(doc)
	rootNode := exportNode(doc.Root, ir.BBox{}, &localID)
	designFrame := canvas.CanvasNode{
		GUID:      nextGUID(&localID),
		Type:      "FRAME",
		Name:      designName,
		Visible:   true,
		Transform: identityTransform(0, 0),
		Size:      canvas.Size{X: float64(max(1, doc.Root.FigmaBBox.Width)), Y: float64(max(1, doc.Root.FigmaBBox.Height))},
		Children:  []canvas.CanvasNode{rootNode},
	}
	page := canvas.CanvasNode{
		GUID:      nextGUID(&localID),
		Type:      "CANVAS",
		Name:      "Page 1",
		Visible:   true,
		Transform: identityTransform(0, 0),
		Size:      designFrame.Size,
		Children:  []canvas.CanvasNode{designFrame},
	}
	root := canvas.CanvasNode{
		GUID:      nextGUID(&localID),
		Type:      "DOCUMENT",
		Name:      "Document",
		Visible:   true,
		Transform: identityTransform(0, 0),
		Size:      designFrame.Size,
		Children:  []canvas.CanvasNode{page},
	}
	result := Result{
		Document: Document{
			Version: canvasVersion,
			Root:    root,
			Blobs:   map[string]any{},
		},
		Report: Report{
			SchemaName:      "CodiaCanvasExport",
			Version:         "1.0",
			NodeCount:       doc.Summary.NodeCount,
			CanvasVersion:   canvasVersion,
			DesignFrameName: designName,
			RootName:        doc.Root.VisibleName,
			UnsupportedNotes: []string{
				"commandsBlob is omitted because it is Figma-internal command history.",
				"fillGeometry and strokeGeometry are omitted because derived vector geometry is not recoverable from Codia IR.",
				"image blob hashes are deterministic placeholders when the source IR does not carry real Figma blob hashes.",
				"derived glyph geometry is omitted; textData, fontName, fontSize, lineHeight, and vertical alignment are exported instead.",
			},
		},
	}
	return result, nil
}

func exportNode(node ir.Node, parent ir.BBox, localID *int) canvas.CanvasNode {
	box := node.FigmaBBox
	if box.Width == 0 && box.Height == 0 {
		box = node.SourceBBox
	}
	relative := ir.BBox{X: box.X - parent.X, Y: box.Y - parent.Y, Width: box.Width, Height: box.Height}
	out := canvas.CanvasNode{
		GUID:       nextGUID(localID),
		Type:       string(node.FigmaType),
		Name:       visibleName(node),
		Visible:    true,
		Transform:  identityTransform(relative.X, relative.Y),
		Size:       canvas.Size{X: float64(max(1, relative.Width)), Y: float64(max(1, relative.Height))},
		PluginData: []canvas.PluginDatum{{PluginID: schemaPluginID, Key: schemaPluginKey, Value: schemaID(node)}},
		FillPaints: paints(node),
	}
	if node.Role == ir.RoleTextView {
		characters := ""
		if node.Text != nil {
			characters = node.Text.Characters
		}
		out.TextData = &canvas.TextData{Characters: characters}
		out.FontName = fontName(node)
		out.FontSize = fontSize(node)
		out.LineHeight = lineHeight(node)
		out.TextAlignVertical = textAlignVertical(node)
		out.TextAutoResize = "WIDTH_AND_HEIGHT"
	}
	if radius := node.Style.CornerRadius; radius != nil {
		out.RectTopLeftRadius = floatPtr(radius.TopLeft)
		out.RectTopRightRadius = floatPtr(radius.TopRight)
		out.RectBottomLeftRadius = floatPtr(radius.BottomLeft)
		out.RectBottomRightRadius = floatPtr(radius.BottomRight)
		out.RectRadiiIndependent = radius.Independent
	}
	for _, child := range node.Children {
		out.Children = append(out.Children, exportNode(child, box, localID))
	}
	return out
}

func designFrameName(doc ir.Document) string {
	if doc.Source.DesignFrameName != "" && strings.HasPrefix(doc.Source.DesignFrameName, "Figma design -") {
		return doc.Source.DesignFrameName
	}
	name := filepath.Base(doc.Source.InputPath)
	if name == "." || name == "/" || name == "" {
		name = "generated"
	}
	return "Figma design - " + name
}

func visibleName(node ir.Node) string {
	if node.Role == ir.RoleTextView && node.Text != nil {
		return node.Text.Characters
	}
	if node.VisibleName != "" {
		return node.VisibleName
	}
	switch node.Role {
	case ir.RoleRoot:
		return "Root"
	case ir.RoleImageView:
		return "Image"
	case ir.RoleBackground, ir.RoleBgButton, ir.RoleBgEditText:
		return "Background"
	case ir.RoleButton:
		return "Button"
	case ir.RoleEditText:
		return "Text"
	default:
		return "Groups"
	}
}

func schemaID(node ir.Node) string {
	if node.SchemaID != "" {
		return node.SchemaID
	}
	if node.Role == ir.RoleRoot {
		return "root_0"
	}
	return fmt.Sprintf("%s_%d_%d_%d", node.Role, node.SourceBBox.X, node.SourceBBox.Y, node.Seq)
}

func paints(node ir.Node) []canvas.Paint {
	if len(node.Style.FillPaints) > 0 {
		out := make([]canvas.Paint, 0, len(node.Style.FillPaints))
		for _, paint := range node.Style.FillPaints {
			out = append(out, convertPaint(paint, node))
		}
		return out
	}
	switch node.Role {
	case ir.RoleImageView:
		return []canvas.Paint{{Type: "IMAGE", Image: imageRef(node)}}
	case ir.RoleBackground, ir.RoleBgButton, ir.RoleBgEditText:
		return []canvas.Paint{{Type: "SOLID", Color: &canvas.Color{R: 1, G: 1, B: 1, A: 1}}}
	default:
		return nil
	}
}

func convertPaint(paint ir.Paint, node ir.Node) canvas.Paint {
	out := canvas.Paint{Type: paint.Type}
	if out.Type == "" {
		out.Type = "SOLID"
	}
	if paint.Color != nil {
		out.Color = &canvas.Color{R: paint.Color.R, G: paint.Color.G, B: paint.Color.B, A: paint.Color.A}
	}
	if out.Type == "IMAGE" || node.Role == ir.RoleImageView {
		out.Type = "IMAGE"
		out.Image = imageRef(node)
		out.Color = nil
	}
	return out
}

func imageRef(node ir.Node) *canvas.ImageRef {
	hash := deterministicHash(schemaID(node))
	if node.Asset != nil && node.Asset.Hash != "" {
		hash = deterministicHash(node.Asset.Hash)
	}
	return &canvas.ImageRef{Hash: hash, Name: schemaID(node)}
}

func deterministicHash(value string) []int {
	if value == "" {
		value = "empty"
	}
	out := make([]int, 8)
	for i, r := range value {
		out[i%len(out)] = (out[i%len(out)]*31 + int(r)) % 256
	}
	return out
}

func fontName(node ir.Node) *canvas.FontName {
	if node.Style.Font != nil {
		return &canvas.FontName{Family: fallback(node.Style.Font.Family, "PingFang SC"), Style: fallback(node.Style.Font.Style, "Regular"), Postscript: node.Style.Font.Postscript}
	}
	return &canvas.FontName{Family: "PingFang SC", Style: "Regular", Postscript: "PingFangSC-Regular"}
}

func fontSize(node ir.Node) float64 {
	if node.Style.Font != nil && node.Style.Font.Size > 0 {
		return node.Style.Font.Size
	}
	return maxFloat(10, float64(node.SourceBBox.Height))
}

func lineHeight(node ir.Node) *canvas.LineHeight {
	if node.Style.LineHeight != nil {
		return &canvas.LineHeight{Value: node.Style.LineHeight.Value, Units: node.Style.LineHeight.Units}
	}
	return &canvas.LineHeight{Value: fontSize(node) * 1.2, Units: "PIXELS"}
}

func textAlignVertical(node ir.Node) string {
	if node.Style.TextAlignVert != "" {
		return node.Style.TextAlignVert
	}
	return "CENTER"
}

func identityTransform(x int, y int) canvas.Transform {
	return canvas.Transform{M00: 1, M01: 0, M02: float64(x), M10: 0, M11: 1, M12: float64(y)}
}

func nextGUID(localID *int) *canvas.GUID {
	id := *localID
	*localID = *localID + 1
	return &canvas.GUID{SessionID: 1, LocalID: id}
}

func floatPtr(value float64) *float64 {
	return &value
}

func fallback(value string, fallbackValue string) string {
	if value == "" {
		return fallbackValue
	}
	return value
}

func max(a, b int) int {
	if a > b {
		return a
	}
	return b
}

func maxFloat(a, b float64) float64 {
	if a > b {
		return a
	}
	return b
}
