package visualtree

import "fmt"

func buildVisualElement(root Node) VisualElement {
	return nodeToVisualElement(root, root.BBox.X, root.BBox.Y)
}

func nodeToVisualElement(node Node, parentX int, parentY int) VisualElement {
	x := node.BBox.X - parentX
	y := node.BBox.Y - parentY
	if node.Type == "Body" {
		x = node.BBox.X
		y = node.BBox.Y
	}
	element := VisualElement{
		ElementID:   node.ID,
		ElementName: visualElementName(node),
		ElementType: node.Type,
		DisplayName: visualElementDisplayName(node),
		LayoutConfig: LayoutConfiguration{
			PositionMode: "Absolute",
			AbsoluteAttrs: AbsoluteAttrs{
				Align:      []string{"LEFT", "TOP"},
				Coord:      []int{x, y},
				OrginCoord: []int{node.BBox.X, node.BBox.Y},
			},
		},
		StyleConfig: VisualStyle{
			WidthSpec:    SizeSpec{Sizing: "FIXED", Value: node.BBox.Width},
			HeightSpec:   SizeSpec{Sizing: "FIXED", Value: node.BBox.Height},
			OpacityLevel: 255,
		},
		ProcessingMeta: ProcessingMeta{
			SourceNodeID:       node.ID,
			SourceTokenIDs:     append([]string(nil), node.SourceRefs.TokenIDs...),
			SourceRelationIDs:  append([]string(nil), node.SourceRefs.RelationIDs...),
			Synthetic:          node.Meta.Synthetic,
			GroupKind:          node.Meta.GroupKind,
			ParentReason:       node.Meta.ParentReason,
			BackgroundTokenIDs: append([]string(nil), node.SourceRefs.BackgroundIDs...),
		},
		BoundingBox: []int{node.BBox.X, node.BBox.Y, node.BBox.Width, node.BBox.Height},
	}
	if node.Style.BackgroundRef != "" {
		element.StyleConfig.BackgroundSpec = &BackgroundSpec{
			Type:               "IMAGE",
			ImageSource:        fmt.Sprintf("token:%s", node.Style.BackgroundRef),
			BackgroundSize:     "cover",
			BackgroundPosition: "center",
			BackgroundRepeat:   "no-repeat",
		}
	}
	switch node.Type {
	case "Text":
		element.ContentData = &ElementContent{TextValue: node.Content.Text}
		element.StyleConfig.TextConfig = &TextConfig{
			FontSize:      max(1, node.BBox.Height),
			FontStyle:     "normal",
			TextAlign:     []string{"LEFT", "TOP"},
			FontFamily:    "Inter",
			LineHeight:    1,
			LetterSpacing: 0,
		}
	case "Image":
		element.ContentData = &ElementContent{ImageSource: visualImageSource(node)}
	}
	for _, child := range node.Children {
		element.ChildElements = append(element.ChildElements, nodeToVisualElement(child, node.BBox.X, node.BBox.Y))
	}
	return element
}

func visualElementName(node Node) string {
	if node.Type == "Body" {
		return "Root"
	}
	if node.Type == "Text" && node.Content.Text != "" {
		return node.Content.Text
	}
	if isBackgroundLeaf(node) {
		return "Background"
	}
	if node.Type == "Layer" {
		if node.Meta.GroupKind == "contained_pair_group" || node.Meta.GroupKind == "text_background_group" {
			return "Button"
		}
		return "Groups"
	}
	return node.Type
}

func visualElementDisplayName(node Node) string {
	if node.Name != "" {
		return node.Name
	}
	return node.ID
}

func visualImageSource(node Node) string {
	if len(node.SourceRefs.BackgroundIDs) > 0 {
		return "token:" + node.SourceRefs.BackgroundIDs[0]
	}
	if len(node.SourceRefs.TokenIDs) > 0 {
		return "token:" + node.SourceRefs.TokenIDs[0]
	}
	return "node:" + node.ID
}
