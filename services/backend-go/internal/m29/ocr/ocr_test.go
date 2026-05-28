package ocr

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/contract"
)

func TestReadAcceptsMinimalObjectBBox(t *testing.T) {
	tmp := t.TempDir()
	path := filepath.Join(tmp, "ocr.json")
	if err := os.WriteFile(path, []byte(`{"image":{"width":100,"height":80},"blocks":[{"id":"ocr_1","text":"A","bbox":{"x":1,"y":2,"width":10,"height":20}}]}`), 0o644); err != nil {
		t.Fatal(err)
	}

	doc, err := Read(path)
	if err != nil {
		t.Fatal(err)
	}
	if doc.Blocks[0].BBox != (contract.BBox{X: 1, Y: 2, Width: 10, Height: 20}) {
		t.Fatalf("unexpected bbox: %#v", doc.Blocks[0].BBox)
	}
}

func TestReadAcceptsPythonOCRListBBox(t *testing.T) {
	tmp := t.TempDir()
	path := filepath.Join(tmp, "ocr.json")
	if err := os.WriteFile(path, []byte(`{"imageSize":{"width":100,"height":80},"blocks":[{"id":"ocr_1","text":"A","bbox":[1,2,10,20],"confidence":0.9}]}`), 0o644); err != nil {
		t.Fatal(err)
	}

	doc, err := Read(path)
	if err != nil {
		t.Fatal(err)
	}
	if doc.Image.Width != 100 || doc.Image.Height != 80 {
		t.Fatalf("unexpected image: %#v", doc.Image)
	}
	if doc.Blocks[0].BBox != (contract.BBox{X: 1, Y: 2, Width: 10, Height: 20}) {
		t.Fatalf("unexpected bbox: %#v", doc.Blocks[0].BBox)
	}
}
