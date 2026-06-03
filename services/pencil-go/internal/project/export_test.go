package project

import (
	"archive/zip"
	"encoding/json"
	"image"
	"image/color"
	"image/draw"
	"image/png"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/luqing-studio/image-figma/services/pencil-go/internal/pencil"
)

func TestExportProjectWritesNamespacedModesAndDebugZip(t *testing.T) {
	tmp := t.TempDir()
	inputA := filepath.Join(tmp, "screen-a.png")
	inputB := filepath.Join(tmp, "screen-b.png")
	writeProjectPNG(t, inputA, 120, 180, color.RGBA{R: 240, G: 242, B: 245, A: 255}, color.RGBA{R: 45, G: 120, B: 220, A: 255})
	writeProjectPNG(t, inputB, 120, 180, color.RGBA{R: 250, G: 250, B: 250, A: 255}, color.RGBA{R: 20, G: 160, B: 120, A: 255})

	outDir := filepath.Join(tmp, "out")
	result, err := Export(Options{
		Inputs:       []string{inputA, inputB},
		OutputDir:    outDir,
		ProjectName:  "Test Project",
		Mode:         pencil.ModeAll,
		Columns:      "2",
		IncludeDebug: true,
		OCRProvider:  "none",
	})
	if err != nil {
		t.Fatalf("Export() error = %v", err)
	}
	if result.Manifest.PageCount != 2 {
		t.Fatalf("page count = %d", result.Manifest.PageCount)
	}
	if len(result.Manifest.Modes) != 3 {
		t.Fatalf("modes = %#v", result.Manifest.Modes)
	}
	assertExists(t, filepath.Join(outDir, "debug", "pages", "page_0001", "m29_physical_evidence.v1.json"))
	assertExists(t, filepath.Join(outDir, "debug", "pages", "page_0002", "m29_physical_evidence.v1.json"))

	for _, mode := range []pencil.Mode{pencil.ModeCleanEditable, pencil.ModeVisualFidelity, pencil.ModeVisualOCR} {
		policy, _ := pencil.PolicyForMode(mode)
		penPath := filepath.Join(outDir, policy.DirName, "design.pen")
		assertExists(t, penPath)
		doc := readPen(t, penPath)
		if len(doc.Children) != 2 {
			t.Fatalf("%s frame count = %d", mode, len(doc.Children))
		}
		ids := map[string]bool{}
		var urls []string
		collectPenIDsAndURLs(doc.Children, ids, &urls, t)
		for id := range ids {
			if !strings.HasPrefix(id, "page_0001__") && !strings.HasPrefix(id, "page_0002__") {
				t.Fatalf("%s has non-namespaced id %q", mode, id)
			}
		}
		if len(urls) == 0 {
			t.Fatalf("%s should contain visible asset URLs", mode)
		}
		for _, url := range urls {
			if !strings.HasPrefix(url, "./assets/visible/page_") {
				t.Fatalf("%s asset URL is not page-namespaced: %s", mode, url)
			}
			if strings.Contains(url, "source.png") || strings.Contains(url, "masks/") || strings.Contains(url, "crops/") {
				t.Fatalf("%s asset URL leaks debug/raw asset: %s", mode, url)
			}
		}
	}

	entries := zipEntries(t, result.ZipPath)
	for _, expected := range []string{
		"manifest.json",
		"clean-editable/design.pen",
		"visual-fidelity/design.pen",
		"visual-ocr/design.pen",
		"debug/report.md",
		"debug/pages/page_0001/m29_physical_evidence.v1.json",
		"debug/pages/page_0002/m29_physical_evidence.v1.json",
	} {
		if !entries[expected] {
			t.Fatalf("zip missing %s", expected)
		}
	}
}

func TestExportProjectExcludesWorkDirWhenDebugDisabled(t *testing.T) {
	tmp := t.TempDir()
	input := filepath.Join(tmp, "screen.png")
	writeProjectPNG(t, input, 100, 140, color.RGBA{R: 245, G: 245, B: 245, A: 255}, color.RGBA{R: 180, G: 70, B: 90, A: 255})

	result, err := Export(Options{
		Inputs:       []string{input},
		OutputDir:    filepath.Join(tmp, "out"),
		ProjectName:  "No Debug",
		Mode:         pencil.ModeVisualFidelity,
		Columns:      "auto",
		IncludeDebug: false,
		OCRProvider:  "none",
	})
	if err != nil {
		t.Fatalf("Export() error = %v", err)
	}
	entries := zipEntries(t, result.ZipPath)
	for entry := range entries {
		if strings.HasPrefix(entry, ".work/") || strings.HasPrefix(entry, "debug/") {
			t.Fatalf("zip should not contain debug/work entry when includeDebug=false: %s", entry)
		}
	}
	if !entries["visual-fidelity/design.pen"] {
		t.Fatalf("zip missing visual-fidelity design")
	}
}

func writeProjectPNG(t *testing.T, path string, width, height int, bg, accent color.RGBA) {
	t.Helper()
	img := image.NewRGBA(image.Rect(0, 0, width, height))
	draw.Draw(img, img.Bounds(), &image.Uniform{C: bg}, image.Point{}, draw.Src)
	draw.Draw(img, image.Rect(18, 22, width-18, 58), &image.Uniform{C: accent}, image.Point{}, draw.Src)
	draw.Draw(img, image.Rect(24, 86, width-24, height-24), &image.Uniform{C: color.RGBA{R: 30, G: 34, B: 42, A: 255}}, image.Point{}, draw.Src)
	file, err := os.Create(path)
	if err != nil {
		t.Fatal(err)
	}
	defer file.Close()
	if err := png.Encode(file, img); err != nil {
		t.Fatal(err)
	}
}

func readPen(t *testing.T, path string) pencil.Document {
	t.Helper()
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	var doc pencil.Document
	if err := json.Unmarshal(data, &doc); err != nil {
		t.Fatal(err)
	}
	return doc
}

func collectPenIDsAndURLs(nodes []pencil.Node, ids map[string]bool, urls *[]string, t *testing.T) {
	t.Helper()
	for _, node := range nodes {
		id, _ := node["id"].(string)
		if id == "" {
			t.Fatalf("node missing id: %#v", node)
		}
		if ids[id] {
			t.Fatalf("duplicate node id %q", id)
		}
		ids[id] = true
		if fill, ok := node["fill"].(map[string]any); ok {
			if url, ok := fill["url"].(string); ok {
				*urls = append(*urls, url)
			}
		}
		if children, ok := node["children"].([]any); ok {
			childNodes := make([]pencil.Node, 0, len(children))
			for _, child := range children {
				child, ok := child.(map[string]any)
				if !ok {
					t.Fatalf("child is not object: %#v", child)
				}
				childNodes = append(childNodes, pencil.Node(child))
			}
			collectPenIDsAndURLs(childNodes, ids, urls, t)
		}
	}
}

func zipEntries(t *testing.T, path string) map[string]bool {
	t.Helper()
	reader, err := zip.OpenReader(path)
	if err != nil {
		t.Fatal(err)
	}
	defer reader.Close()
	out := map[string]bool{}
	for _, file := range reader.File {
		out[file.Name] = true
	}
	return out
}

func assertExists(t *testing.T, path string) {
	t.Helper()
	if _, err := os.Stat(path); err != nil {
		t.Fatalf("expected %s: %v", path, err)
	}
}
