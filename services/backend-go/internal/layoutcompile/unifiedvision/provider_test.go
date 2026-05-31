package unifiedvision

import (
	"context"
	"encoding/json"
	"image"
	"image/color"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

func TestProviderSendsCurlUserAgentAndRetries(t *testing.T) {
	attempts := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		attempts++
		if got := r.Header.Get("User-Agent"); got != "curl/8.7.1" {
			t.Fatalf("user agent = %q", got)
		}
		if got := r.Header.Get("Accept"); got != "application/json" {
			t.Fatalf("accept = %q", got)
		}
		if attempts == 1 {
			http.Error(w, "temporary", http.StatusInternalServerError)
			return
		}
		_ = json.NewEncoder(w).Encode(map[string]any{
			"output_text": `{"version":"unified_vision_result.v1","groups":[]}`,
		})
	}))
	defer server.Close()

	client := newProviderClient(Options{
		WireAPI:          "responses",
		BaseURL:          server.URL,
		APIKey:           "key",
		Model:            "model",
		Timeout:          5 * time.Second,
		TransportRetries: 2,
	})
	img := image.NewRGBA(image.Rect(0, 0, 2, 2))
	img.Set(0, 0, color.RGBA{A: 255})
	resp, err := client.call(context.Background(), "prompt", img)
	if err != nil {
		t.Fatalf("call error = %v", err)
	}
	if !strings.Contains(resp.Text, "unified_vision_result.v1") {
		t.Fatalf("response text = %q", resp.Text)
	}
	if attempts != 2 {
		t.Fatalf("attempts = %d, want 2", attempts)
	}
}
