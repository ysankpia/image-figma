package detector

import (
	"bytes"
	"context"
	"encoding/json"
	"image"
	"image/color"
	"image/png"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"sync/atomic"
	"testing"
	"time"
)

func TestRunExecutesPassesConcurrentlyAndKeepsStablePassOrder(t *testing.T) {
	var inFlight int32
	var maxInFlight int32
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		current := atomic.AddInt32(&inFlight, 1)
		for {
			observed := atomic.LoadInt32(&maxInFlight)
			if current <= observed || atomic.CompareAndSwapInt32(&maxInFlight, observed, current) {
				break
			}
		}
		defer atomic.AddInt32(&inFlight, -1)
		time.Sleep(80 * time.Millisecond)
		_ = json.NewEncoder(w).Encode(map[string]any{
			"output_text": `{"elements":[]}`,
		})
	}))
	defer srv.Close()

	input := filepath.Join(t.TempDir(), "input.png")
	writeTestPNG(t, input)
	out := t.TempDir()
	result, err := Run(context.Background(), Options{
		InputPath:   input,
		OutputDir:   out,
		WireAPI:     "responses",
		BaseURL:     srv.URL,
		APIKey:      "test-key",
		Model:       "test-model",
		Passes:      []string{"layout", "imageview"},
		Concurrency: 2,
		Timeout:     time.Second,
	})
	if err != nil {
		t.Fatalf("run detector: %v", err)
	}
	if atomic.LoadInt32(&maxInFlight) < 2 {
		t.Fatalf("expected concurrent pass execution, max in flight = %d", maxInFlight)
	}
	passes := result.Document.Preprocess.Passes
	if len(passes) != 2 || passes[0].ID != "layout" || passes[1].ID != "imageview" {
		t.Fatalf("pass order was not stable: %+v", passes)
	}
	for _, raw := range result.Artifacts.RawResponses {
		if _, err := os.Stat(filepath.Join(out, raw)); err != nil {
			t.Fatalf("raw artifact %s was not written: %v", raw, err)
		}
	}
}

func writeTestPNG(t *testing.T, path string) {
	t.Helper()
	img := image.NewRGBA(image.Rect(0, 0, 32, 64))
	for y := 0; y < 64; y++ {
		for x := 0; x < 32; x++ {
			img.Set(x, y, color.RGBA{R: uint8(x), G: uint8(y), B: 200, A: 255})
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
