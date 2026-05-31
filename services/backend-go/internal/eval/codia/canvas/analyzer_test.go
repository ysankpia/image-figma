package canvas

import (
	"os"
	"path/filepath"
	"testing"
)

func TestAnalyzeParsesSchemaBBoxOrderingAndControls(t *testing.T) {
	doc := CanvasDocument{
		Version: 101,
		Root: CanvasNode{
			Type: "DOCUMENT",
			Name: "Document",
			Children: []CanvasNode{
				{
					Type: "CANVAS",
					Name: "Page 1",
					Children: []CanvasNode{
						{
							Type: "FRAME",
							Name: "Figma design - sample.png",
							Size: Size{X: 100, Y: 100},
							Children: []CanvasNode{
								{
									GUID:       &GUID{SessionID: 1, LocalID: 1},
									Type:       "FRAME",
									Name:       "Root",
									Size:       Size{X: 100, Y: 100},
									PluginData: schemaData("root_0"),
									Children: []CanvasNode{
										{
											GUID:       &GUID{SessionID: 1, LocalID: 2},
											Type:       "FRAME",
											Name:       "Button",
											Transform:  Transform{M02: 10, M12: 20},
											Size:       Size{X: 40, Y: 20},
											PluginData: schemaData("Button_10_20_3"),
											Children: []CanvasNode{
												{
													GUID:       &GUID{SessionID: 1, LocalID: 3},
													Type:       "TEXT",
													Name:       "Go",
													Transform:  Transform{M02: 4, M12: 3},
													Size:       Size{X: 20, Y: 10},
													PluginData: schemaData("TextView_14_23_5"),
													TextData:   &TextData{Characters: "Go"},
													FontName:   &FontName{Family: "Inter", Style: "Regular"},
													FontSize:   10,
													LineHeight: &LineHeight{Value: 100, Units: "PERCENT"},
												},
												{
													GUID:                  &GUID{SessionID: 1, LocalID: 4},
													Type:                  "ROUNDED_RECTANGLE",
													Name:                  "Background",
													Size:                  Size{X: 40, Y: 20},
													PluginData:            schemaData("bg_Button_10_20_4"),
													FillPaints:            []Paint{{Type: "SOLID"}},
													RectTopLeftRadius:     floatPtr(8),
													RectTopRightRadius:    floatPtr(8),
													RectBottomLeftRadius:  floatPtr(8),
													RectBottomRightRadius: floatPtr(8),
													RectRadiiIndependent:  true,
												},
											},
										},
										{
											GUID:       &GUID{SessionID: 1, LocalID: 5},
											Type:       "ROUNDED_RECTANGLE",
											Name:       "Background",
											Transform:  Transform{M02: 0, M12: 90},
											Size:       Size{X: 100, Y: 10},
											PluginData: schemaData("Background_0_90_1"),
											FillPaints: []Paint{{Type: "IMAGE", Image: &ImageRef{Hash: []int{1, 2, 3}}}},
										},
									},
								},
							},
						},
					},
				},
			},
		},
	}

	analysis, err := Analyze(doc, "inline", "")
	if err != nil {
		t.Fatalf("Analyze() error = %v", err)
	}
	if analysis.NodeCount != 5 || analysis.RootChildCount != 2 || analysis.MaxDepth != 2 {
		t.Fatalf("unexpected structure counts: %#v", analysis)
	}
	if analysis.RootBBox.Width != 100 || analysis.RootBBox.Height != 100 {
		t.Fatalf("unexpected root bbox: %#v", analysis.RootBBox)
	}
	if analysis.RoleCounts["Button"] != 1 || analysis.RoleCounts["bg_Button"] != 1 || analysis.RoleCounts["TextView"] != 1 {
		t.Fatalf("unexpected role counts: %#v", analysis.RoleCounts)
	}
	if analysis.Suffix.Min != 0 || analysis.Suffix.Max != 5 || len(analysis.Suffix.Missing) != 1 || analysis.Suffix.Missing[0] != 2 {
		t.Fatalf("unexpected suffix report: %#v", analysis.Suffix)
	}
	if analysis.ChildOrder.MultiChildParents != 2 || analysis.ChildOrder.StrictDescendingParents != 2 {
		t.Fatalf("expected descending child order, got %#v", analysis.ChildOrder)
	}
	if analysis.LastChild["bg_Button"].Last != 1 || analysis.LastChild["Background"].Last != 1 {
		t.Fatalf("expected backgrounds to be last children: %#v", analysis.LastChild)
	}
	if analysis.ButtonModes["TextView+bg_Button"] != 1 {
		t.Fatalf("unexpected button modes: %#v", analysis.ButtonModes)
	}
	if analysis.Text.NameCharacterMatch != 1 || analysis.ImageFills.ImageFillCount != 1 || analysis.ImageFills.UniqueHashCount != 1 {
		t.Fatalf("unexpected text/image reports: text=%#v image=%#v", analysis.Text, analysis.ImageFills)
	}
	if analysis.CornerRadius.NodeCount != 1 || analysis.CornerRadius.ByRole["bg_Button"] != 1 {
		t.Fatalf("unexpected corner radius report: %#v", analysis.CornerRadius)
	}
}

func TestAnalyzeReportsRoleMappingViolations(t *testing.T) {
	doc := minimalDoc(CanvasNode{
		Type:       "FRAME",
		Name:       "Groups",
		Size:       Size{X: 100, Y: 100},
		PluginData: schemaData("root_0"),
	})
	analysis, err := Analyze(doc, "inline", "")
	if err != nil {
		t.Fatalf("Analyze() error = %v", err)
	}
	if len(analysis.RoleMappingViolations) != 1 || analysis.RoleMappingViolations[0].Reason != "name_mismatch" {
		t.Fatalf("expected root name violation, got %#v", analysis.RoleMappingViolations)
	}
}

func TestWriteArtifactsWritesJSONAndMarkdown(t *testing.T) {
	tmp := t.TempDir()
	analysis, err := Analyze(minimalDoc(CanvasNode{
		Type:       "FRAME",
		Name:       "Root",
		Size:       Size{X: 100, Y: 100},
		PluginData: schemaData("root_0"),
	}), "inline", "")
	if err != nil {
		t.Fatalf("Analyze() error = %v", err)
	}
	if err := WriteArtifacts(tmp, analysis); err != nil {
		t.Fatalf("WriteArtifacts() error = %v", err)
	}
	for _, name := range []string{"codia_canvas_analysis.v1.json", "codia_canvas_analysis_report.md"} {
		if _, err := os.Stat(filepath.Join(tmp, name)); err != nil {
			t.Fatalf("expected artifact %s: %v", name, err)
		}
	}
}

func TestExpectationTencentComic018FailsOnWrongInput(t *testing.T) {
	analysis, err := Analyze(minimalDoc(CanvasNode{
		Type:       "FRAME",
		Name:       "Root",
		Size:       Size{X: 100, Y: 100},
		PluginData: schemaData("root_0"),
	}), "inline", ExpectTencentComic018)
	if err != nil {
		t.Fatalf("Analyze() error = %v", err)
	}
	if len(analysis.ExpectationFailures) == 0 {
		t.Fatalf("expected tencent-comic-018 expectation to fail on minimal input")
	}
}

func minimalDoc(root CanvasNode) CanvasDocument {
	return CanvasDocument{
		Version: 101,
		Root: CanvasNode{
			Type: "DOCUMENT",
			Name: "Document",
			Children: []CanvasNode{
				{
					Type: "CANVAS",
					Name: "Page 1",
					Children: []CanvasNode{
						{
							Type:     "FRAME",
							Name:     "Figma design - sample.png",
							Size:     Size{X: 100, Y: 100},
							Children: []CanvasNode{root},
						},
					},
				},
			},
		},
	}
}

func schemaData(value string) []PluginDatum {
	return []PluginDatum{{PluginID: "1329812760871373657", Key: "schema:id", Value: value}}
}

func floatPtr(value float64) *float64 {
	return &value
}
