package emitter

import (
	"fmt"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/ir"
)

const (
	SchemaName = "CodiaFigmaLikeTree"
	Version    = "1.0"
)

func Emit(doc ir.Document) (Document, error) {
	if doc.SchemaName != ir.SchemaName {
		return Document{}, fmt.Errorf("expected %s, got %q", ir.SchemaName, doc.SchemaName)
	}
	root := emitNode(doc.Root, ir.BBox{})
	out := Document{
		SchemaName: SchemaName,
		Version:    Version,
		Source: Source{
			IRSchemaName: doc.SchemaName,
			IRVersion:    doc.Version,
			InputPath:    doc.Source.InputPath,
			RootPath:     doc.Source.RootPath,
		},
		Root: root,
		Summary: Summary{
			NodeCount:       doc.Summary.NodeCount,
			MaxDepth:        doc.Summary.MaxDepth,
			RoleCounts:      cloneCounts(doc.Summary.RoleCounts),
			FigmaTypeCounts: cloneCounts(doc.Summary.FigmaTypeCounts),
		},
	}
	if err := validateEmittedTree(out.Root); err != nil {
		return Document{}, err
	}
	return out, nil
}

func emitNode(node ir.Node, parentBBox ir.BBox) Node {
	out := Node{
		ID:           node.ID,
		Type:         node.FigmaType,
		Name:         node.VisibleName,
		Role:         node.Role,
		SchemaID:     node.SchemaID,
		Seq:          node.Seq,
		SourceBBox:   node.SourceBBox,
		FigmaBBox:    node.FigmaBBox,
		RelativeBBox: relativeBBox(node.FigmaBBox, parentBBox),
		Text:         node.Text,
		Asset:        node.Asset,
		Style:        node.Style,
	}
	for _, child := range node.Children {
		out.Children = append(out.Children, emitNode(child, node.FigmaBBox))
	}
	return out
}

func relativeBBox(child ir.BBox, parent ir.BBox) ir.BBox {
	return ir.BBox{
		X:      child.X - parent.X,
		Y:      child.Y - parent.Y,
		Width:  child.Width,
		Height: child.Height,
	}
}

func validateEmittedTree(root Node) error {
	var walk func(Node) error
	walk = func(node Node) error {
		if !allowedFigmaType(node.Type) {
			return fmt.Errorf("node %s uses unsupported figma type %q", node.ID, node.Type)
		}
		if !visibleNameAllowed(node) {
			return fmt.Errorf("node %s role %q has invalid visible name %q", node.ID, node.Role, node.Name)
		}
		for _, child := range node.Children {
			if err := walk(child); err != nil {
				return err
			}
		}
		return nil
	}
	return walk(root)
}

func allowedFigmaType(value ir.FigmaType) bool {
	switch value {
	case ir.FigmaFrame, ir.FigmaText, ir.FigmaRoundedRectangle:
		return true
	default:
		return false
	}
}

func visibleNameAllowed(node Node) bool {
	switch node.Role {
	case ir.RoleRoot:
		return node.Name == "Root"
	case ir.RoleViewGroup, ir.RoleListView, ir.RoleActionBar, ir.RoleStatusBar, ir.RoleBottomNavigation:
		return node.Name == "Groups"
	case ir.RoleButton:
		return node.Name == "Button"
	case ir.RoleEditText:
		return node.Name == "Text"
	case ir.RoleImageView:
		return node.Name == "Image"
	case ir.RoleBackground, ir.RoleBgButton, ir.RoleBgEditText:
		return node.Name == "Background"
	case ir.RoleTextView:
		return node.Text != nil && node.Name == node.Text.Characters
	default:
		return false
	}
}

func cloneCounts(in map[string]int) map[string]int {
	out := make(map[string]int, len(in))
	for key, value := range in {
		out[key] = value
	}
	return out
}
