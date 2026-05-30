package ir

import (
	"testing"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/canvas"
)

func TestFromAnalysisPreservesRoleDualBBoxTextAndAsset(t *testing.T) {
	analysis, err := canvas.Analyze(canvas.CanvasDocument{
		Version: 101,
		Root: canvas.CanvasNode{
			Type: "DOCUMENT",
			Name: "Document",
			Children: []canvas.CanvasNode{
				{
					Type: "CANVAS",
					Name: "Page 1",
					Children: []canvas.CanvasNode{
						{
							Type: "FRAME",
							Name: "Figma design - sample.png",
							Children: []canvas.CanvasNode{
								{
									GUID:       &canvas.GUID{SessionID: 1, LocalID: 1},
									Type:       "FRAME",
									Name:       "Root",
									Size:       canvas.Size{X: 100, Y: 100},
									PluginData: schemaData("root_0"),
									Children: []canvas.CanvasNode{
										{
											GUID:       &canvas.GUID{SessionID: 1, LocalID: 2},
											Type:       "TEXT",
											Name:       "Hi",
											Transform:  canvas.Transform{M02: 15, M12: 22},
											Size:       canvas.Size{X: 30, Y: 12},
											PluginData: schemaData("TextView_12_22_2"),
											TextData:   &canvas.TextData{Characters: "Hi"},
											FontName:   &canvas.FontName{Family: "Inter", Style: "Regular"},
											FontSize:   12,
										},
										{
											GUID:                  &canvas.GUID{SessionID: 1, LocalID: 3},
											Type:                  "ROUNDED_RECTANGLE",
											Name:                  "Image",
											Transform:             canvas.Transform{M02: 40, M12: 40},
											Size:                  canvas.Size{X: 10, Y: 10},
											PluginData:            schemaData("ImageView_40_40_1"),
											FillPaints:            []canvas.Paint{{Type: "IMAGE", Image: &canvas.ImageRef{Hash: []int{9, 8, 7}}}},
											RectTopLeftRadius:     floatPtr(4),
											RectTopRightRadius:    floatPtr(6),
											RectBottomLeftRadius:  floatPtr(8),
											RectBottomRightRadius: floatPtr(10),
											RectRadiiIndependent:  true,
										},
									},
								},
							},
						},
					},
				},
			},
		},
	}, "inline", "")
	if err != nil {
		t.Fatalf("Analyze() error = %v", err)
	}
	doc, err := FromAnalysis(analysis)
	if err != nil {
		t.Fatalf("FromAnalysis() error = %v", err)
	}
	if doc.SchemaName != SchemaName || doc.Root.Role != RoleRoot || len(doc.Root.Children) != 2 {
		t.Fatalf("unexpected IR root: %#v", doc)
	}
	text := doc.Root.Children[0]
	if text.ID != "TextView_12_22_2" || text.Role != RoleTextView || text.FigmaType != FigmaText {
		t.Fatalf("unexpected text node identity: %#v", text)
	}
	if text.SourceBBox.X != 12 || text.SourceBBox.Y != 22 || text.FigmaBBox.X != 15 || text.FigmaBBox.Y != 22 {
		t.Fatalf("expected source bbox from schema and figma bbox from transform, got source=%#v figma=%#v", text.SourceBBox, text.FigmaBBox)
	}
	if text.Text == nil || text.Text.Characters != "Hi" || text.Style.Font == nil || text.Style.Font.Family != "Inter" {
		t.Fatalf("expected text payload and style, got %#v", text)
	}
	image := doc.Root.Children[1]
	if image.Asset == nil || image.Asset.Kind != "image" || image.Asset.Hash != "9,8,7" {
		t.Fatalf("expected image asset hash, got %#v", image.Asset)
	}
	if image.Style.CornerRadius == nil ||
		image.Style.CornerRadius.TopLeft != 4 ||
		image.Style.CornerRadius.TopRight != 6 ||
		image.Style.CornerRadius.BottomLeft != 8 ||
		image.Style.CornerRadius.BottomRight != 10 ||
		!image.Style.CornerRadius.Independent {
		t.Fatalf("expected corner radius to be preserved, got %#v", image.Style.CornerRadius)
	}
	if doc.Summary.NodeCount != 3 || doc.Summary.RoleCounts["TextView"] != 1 {
		t.Fatalf("unexpected summary: %#v", doc.Summary)
	}
}

func schemaData(value string) []canvas.PluginDatum {
	return []canvas.PluginDatum{{PluginID: "1329812760871373657", Key: "schema:id", Value: value}}
}

func floatPtr(value float64) *float64 {
	return &value
}
