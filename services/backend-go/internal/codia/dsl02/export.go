package dsl02

import (
	"fmt"
	"math"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/emitter"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/ir"
)

const (
	Version = "0.2"
	Kind    = "codia_runtime"
)

func Export(taskID string, doc emitter.Document) (Document, error) {
	if doc.SchemaName != emitter.SchemaName {
		return Document{}, fmt.Errorf("expected %s, got %q", emitter.SchemaName, doc.SchemaName)
	}
	root := convertNode(doc.Root, true)
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
		Assets: []Asset{},
		Root:   root,
		Meta: map[string]any{
			"source":           "go_codiacompile",
			"sourceSchemaName": doc.SchemaName,
			"sourceVersion":    doc.Version,
			"summary":          doc.Summary,
		},
	}, nil
}

func convertNode(node emitter.Node, isRoot bool) Node {
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
		Style:    runtimeStyle(node),
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
	for _, child := range node.Children {
		out.Children = append(out.Children, convertNode(child, false))
	}
	if len(out.Style) == 0 {
		out.Style = nil
	}
	if len(out.Meta) == 0 {
		out.Meta = nil
	}
	return out
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

func runtimeStyle(node emitter.Node) map[string]any {
	style := map[string]any{}
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
	return style
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
