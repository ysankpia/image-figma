package compile

import (
	"bytes"
	"encoding/json"
	"image"
	"image/color"
	"image/png"
	"os"
	"path/filepath"
	"testing"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/draft/contract"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/draft/exportdsl"
)

func TestRunWritesDraftArtifacts(t *testing.T) {
	tmp := t.TempDir()
	input := filepath.Join(tmp, "input.png")
	writePNG(t, input)

	result, err := Run(Options{
		InputPath: input,
		OutputDir: filepath.Join(tmp, "out"),
		TaskID:    "task_test",
	})
	if err != nil {
		t.Fatalf("run: %v", err)
	}
	if result.Graph.Version != contract.Version {
		t.Fatalf("graph version = %q", result.Graph.Version)
	}
	if result.DSL.Version != exportdsl.Version || result.DSL.Kind != exportdsl.Kind {
		t.Fatalf("unexpected dsl identity: %+v", result.DSL)
	}
	assertFile(t, filepath.Join(tmp, "out", result.Artifacts.M29PhysicalEvidence))
	assertFile(t, filepath.Join(tmp, "out", result.Artifacts.EvidenceTokens))
	assertFile(t, filepath.Join(tmp, "out", result.Artifacts.EditableLayerGraph))
	assertFile(t, filepath.Join(tmp, "out", result.Artifacts.ValidationReport))
	assertFile(t, filepath.Join(tmp, "out", result.Artifacts.AssetManifest))
	assertFile(t, filepath.Join(tmp, "out", result.Artifacts.RuntimeDSL))

	data, err := os.ReadFile(filepath.Join(tmp, "out", result.Artifacts.EditableLayerGraph))
	if err != nil {
		t.Fatalf("read graph: %v", err)
	}
	var graph contract.Document
	if err := json.Unmarshal(data, &graph); err != nil {
		t.Fatalf("parse graph: %v", err)
	}
	if len(graph.Layers) < 2 || graph.Layers[0].Kind != contract.LayerReferenceImage || graph.Layers[0].Visible {
		t.Fatalf("expected hidden reference plus visible draft layers, got %+v", graph.Layers)
	}
	if !hasVisibleLayer(graph) {
		t.Fatalf("expected at least one visible editable draft layer, got %+v", graph.Layers)
	}
	for _, asset := range graph.Assets {
		assertFile(t, filepath.Join(tmp, "out", "assets", asset.ID+".png"))
	}
}

func writePNG(t *testing.T, path string) {
	t.Helper()
	img := image.NewRGBA(image.Rect(0, 0, 64, 96))
	for y := 0; y < 96; y++ {
		for x := 0; x < 64; x++ {
			img.Set(x, y, color.RGBA{R: 240, G: 240, B: 240, A: 255})
		}
	}
	for y := 20; y < 40; y++ {
		for x := 12; x < 52; x++ {
			img.Set(x, y, color.RGBA{R: 20, G: 120, B: 220, A: 255})
		}
	}
	var buf bytes.Buffer
	if err := png.Encode(&buf, img); err != nil {
		t.Fatalf("encode png: %v", err)
	}
	if err := os.WriteFile(path, buf.Bytes(), 0o644); err != nil {
		t.Fatalf("write png: %v", err)
	}
}

func assertFile(t *testing.T, path string) {
	t.Helper()
	info, err := os.Stat(path)
	if err != nil {
		t.Fatalf("missing file %s: %v", path, err)
	}
	if info.Size() == 0 {
		t.Fatalf("empty file %s", path)
	}
}

func hasVisibleLayer(graph contract.Document) bool {
	for _, layer := range graph.Layers {
		if layer.Visible && layer.Kind != contract.LayerReferenceImage {
			return true
		}
	}
	return false
}
