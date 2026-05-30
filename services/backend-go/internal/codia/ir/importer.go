package ir

import (
	"fmt"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/canvas"
)

const (
	SchemaName = "CodiaIR"
	Version    = "1.0"
)

func FromAnalysis(analysis canvas.Analysis) (Document, error) {
	rootFact, ok := rootFact(analysis)
	if !ok {
		return Document{}, fmt.Errorf("analysis missing root fact at %q", analysis.RootPath)
	}
	root := nodeFromFact(rootFact)
	doc := Document{
		SchemaName: SchemaName,
		Version:    Version,
		Source: Source{
			InputPath:       analysis.InputPath,
			CanvasVersion:   analysis.CanvasVersion,
			DesignFramePath: analysis.DesignFramePath,
			DesignFrameName: analysis.DesignFrameName,
			RootPath:        analysis.RootPath,
		},
		Root: root,
		Summary: Summary{
			NodeCount:       analysis.NodeCount,
			MaxDepth:        analysis.MaxDepth,
			RoleCounts:      cloneCounts(analysis.RoleCounts),
			FigmaTypeCounts: cloneCounts(analysis.TypeCounts),
		},
	}
	return doc, nil
}

func rootFact(analysis canvas.Analysis) (*canvas.NodeFact, bool) {
	for i := range analysis.Nodes {
		if analysis.Nodes[i].Path == analysis.RootPath {
			return &analysis.Nodes[i], true
		}
	}
	return nil, false
}

func nodeFromFact(fact *canvas.NodeFact) Node {
	node := Node{
		ID:          irID(fact),
		Role:        Role(fact.Role),
		SourceBBox:  sourceBBox(fact),
		FigmaBBox:   bboxFromCanvas(fact.BBox),
		FigmaType:   FigmaType(fact.Type),
		VisibleName: fact.Name,
		SchemaID:    fact.SchemaID,
		Seq:         fact.SchemaSeq,
		HasSeq:      fact.HasSchemaSeq,
		SourceGUID:  fact.GUID,
		SourcePath:  fact.Path,
		Evidence: []Evidence{{
			Kind:       "golden_canvas_node",
			BBox:       bboxFromCanvas(fact.BBox),
			Confidence: 1,
			SourceID:   fact.GUID,
			Notes:      fact.SchemaID,
		}},
		Style: styleFromFact(fact),
	}
	if fact.Role == string(RoleTextView) {
		node.Text = &Text{Characters: fact.TextCharacters}
	}
	if asset := assetFromFact(fact); asset != nil {
		node.Asset = asset
	}
	for _, child := range fact.Children {
		node.Children = append(node.Children, nodeFromFact(child))
	}
	return node
}

func irID(fact *canvas.NodeFact) string {
	if fact.SchemaID != "" {
		return fact.SchemaID
	}
	if fact.GUID != "" {
		return "guid_" + fact.GUID
	}
	return "path_" + fact.Path
}

func sourceBBox(fact *canvas.NodeFact) BBox {
	box := bboxFromCanvas(fact.BBox)
	if fact.HasSchemaSeq && fact.Role != "" {
		box.X = fact.SchemaX
		box.Y = fact.SchemaY
	}
	return box
}

func bboxFromCanvas(box canvas.BBox) BBox {
	return BBox{X: box.X, Y: box.Y, Width: box.Width, Height: box.Height}
}

func styleFromFact(fact *canvas.NodeFact) Style {
	style := Style{
		Visible:       true,
		Opacity:       1,
		TextAlignVert: "",
	}
	if fact.Source != nil {
		style.FillPaints = paintsFromCanvas(fact.Source.FillPaints)
		style.TextAlignVert = fact.Source.TextAlignVertical
		if fact.Source.FontName != nil || fact.Source.FontSize > 0 {
			style.Font = &Font{}
			if fact.Source.FontName != nil {
				style.Font.Family = fact.Source.FontName.Family
				style.Font.Style = fact.Source.FontName.Style
				style.Font.Postscript = fact.Source.FontName.Postscript
			}
			style.Font.Size = fact.Source.FontSize
		}
		if fact.Source.LineHeight != nil {
			style.LineHeight = &LineHeight{Value: fact.Source.LineHeight.Value, Units: fact.Source.LineHeight.Units}
		}
	}
	if fact.CornerRadius != nil {
		style.CornerRadius = &CornerRadius{
			TopLeft:     fact.CornerRadius.TopLeft,
			TopRight:    fact.CornerRadius.TopRight,
			BottomLeft:  fact.CornerRadius.BottomLeft,
			BottomRight: fact.CornerRadius.BottomRight,
			Independent: fact.CornerRadius.Independent,
		}
	}
	return style
}

func paintsFromCanvas(paints []canvas.Paint) []Paint {
	out := make([]Paint, 0, len(paints))
	for _, paint := range paints {
		item := Paint{Type: paint.Type}
		if paint.Color != nil {
			item.Color = &Color{R: paint.Color.R, G: paint.Color.G, B: paint.Color.B, A: paint.Color.A}
		}
		if paint.Image != nil && len(paint.Image.Hash) > 0 {
			item.Hash = hashString(paint.Image.Hash)
		} else if paint.ImageThumbnail != nil && len(paint.ImageThumbnail.Hash) > 0 {
			item.Hash = hashString(paint.ImageThumbnail.Hash)
		}
		out = append(out, item)
	}
	return out
}

func assetFromFact(fact *canvas.NodeFact) *Asset {
	for i, fillType := range fact.FillTypes {
		if fillType != "IMAGE" {
			continue
		}
		asset := &Asset{Kind: "image"}
		if i < len(fact.ImageHashes) {
			asset.Hash = fact.ImageHashes[i]
		}
		return asset
	}
	return nil
}

func hashString(values []int) string {
	if len(values) == 0 {
		return ""
	}
	out := fmt.Sprintf("%d", values[0])
	for _, value := range values[1:] {
		out += fmt.Sprintf(",%d", value)
	}
	return out
}

func cloneCounts(in map[string]int) map[string]int {
	out := make(map[string]int, len(in))
	for key, value := range in {
		out[key] = value
	}
	return out
}
