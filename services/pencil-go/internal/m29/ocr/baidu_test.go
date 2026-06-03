package ocr

import (
	"encoding/json"
	"testing"

	"github.com/luqing-studio/image-figma/services/pencil-go/internal/m29/contract"
)

func TestParsePPOCRV5RowsConvertsBoxesAndFiltersLowConfidence(t *testing.T) {
	rows := []map[string]any{
		{
			"result": map[string]any{
				"ocrResults": []any{
					map[string]any{
						"prunedResult": map[string]any{
							"rec_texts":  []any{"Title", "Noise", "Poly"},
							"rec_scores": []any{0.99, 0.2, 0.92},
							"rec_boxes": []any{
								[]any{396.0, 82.0, 543.0, 124.0},
								[]any{1.0, 1.0, 3.0, 3.0},
								nil,
							},
							"rec_polys": []any{
								[]any{},
								[]any{},
								[]any{
									[]any{10.0, 20.0},
									[]any{50.0, 20.0},
									[]any{50.0, 44.0},
									[]any{10.0, 44.0},
								},
							},
						},
					},
				},
			},
		},
	}

	blocks, warnings := ParsePPOCRV5Rows(rows, 0.7)

	if len(blocks) != 2 {
		t.Fatalf("expected 2 blocks, got %d", len(blocks))
	}
	if blocks[0].Text != "Title" || blocks[1].Text != "Poly" {
		t.Fatalf("unexpected texts: %#v", blocks)
	}
	if blocks[0].BBox != (contract.BBox{X: 396, Y: 82, Width: 147, Height: 42}) {
		t.Fatalf("unexpected first bbox: %#v", blocks[0].BBox)
	}
	if blocks[1].BBox != (contract.BBox{X: 10, Y: 20, Width: 40, Height: 24}) {
		t.Fatalf("unexpected poly bbox: %#v", blocks[1].BBox)
	}
	if len(warnings) != 1 || warnings[0].Code != "OCR_LOW_CONFIDENCE" {
		t.Fatalf("unexpected warnings: %#v", warnings)
	}
}

func TestRecBoxAndPolygonRejectInvalidShapes(t *testing.T) {
	if bbox, ok := RecBoxToBBox([]any{10.0, 20.0, 30.0, 50.0}); !ok || bbox != (contract.BBox{X: 10, Y: 20, Width: 20, Height: 30}) {
		t.Fatalf("unexpected rec bbox %#v ok=%v", bbox, ok)
	}
	if _, ok := RecBoxToBBox([]any{10.0, 20.0, 8.0, 50.0}); ok {
		t.Fatalf("expected inverted box rejection")
	}
	if _, ok := RecBoxToBBox([]any{"bad", 20.0, 30.0, 50.0}); ok {
		t.Fatalf("expected bad number rejection")
	}
	if bbox, ok := PolygonToBBox([]any{[]any{1.0, 2.0}, []any{5.0, 2.0}, []any{5.0, 8.0}, []any{1.0, 8.0}}); !ok || bbox != (contract.BBox{X: 1, Y: 2, Width: 4, Height: 6}) {
		t.Fatalf("unexpected poly bbox %#v ok=%v", bbox, ok)
	}
	if _, ok := PolygonToBBox([]any{[]any{1.0, 2.0}}); ok {
		t.Fatalf("expected one-point polygon rejection")
	}
}

func TestParsePPOCRV5RowsWithJSONDecodedNumbers(t *testing.T) {
	payload := `{"result":{"ocrResults":[{"prunedResult":{"rec_texts":["A"],"rec_scores":[0.9],"rec_boxes":[[1,2,11,22]],"rec_polys":[]}}]}}`
	var row map[string]any
	if err := json.Unmarshal([]byte(payload), &row); err != nil {
		t.Fatal(err)
	}
	blocks, warnings := ParsePPOCRV5Rows([]map[string]any{row}, 0.7)
	if len(warnings) != 0 {
		t.Fatalf("unexpected warnings: %#v", warnings)
	}
	if len(blocks) != 1 || blocks[0].BBox != (contract.BBox{X: 1, Y: 2, Width: 10, Height: 20}) {
		t.Fatalf("unexpected blocks: %#v", blocks)
	}
}
