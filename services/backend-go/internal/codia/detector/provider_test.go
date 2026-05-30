package detector

import (
	"context"
	"encoding/json"
	"image"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

func TestProviderResponsesStreamExtractsDeltas(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/v1/responses" {
			t.Fatalf("path = %s", r.URL.Path)
		}
		var payload map[string]any
		if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
			t.Fatalf("decode payload: %v", err)
		}
		if payload["stream"] != true {
			t.Fatalf("expected stream=true, got %#v", payload["stream"])
		}
		w.Header().Set("Content-Type", "text/event-stream")
		_, _ = w.Write([]byte("event: response.output_text.delta\n"))
		_, _ = w.Write([]byte("data: {\"type\":\"response.output_text.delta\",\"delta\":\"{\\\"elements\\\":\"}\n\n"))
		_, _ = w.Write([]byte("event: response.output_text.delta\n"))
		_, _ = w.Write([]byte("data: {\"type\":\"response.output_text.delta\",\"delta\":\"[]}\"}\n\n"))
		_, _ = w.Write([]byte("data: [DONE]\n\n"))
	}))
	defer srv.Close()

	client := newProviderClient(Options{
		WireAPI: "responses",
		BaseURL: srv.URL,
		APIKey:  "test-key",
		Model:   "test-model",
		Timeout: time.Second,
		Stream:  true,
	})
	response, err := client.detect(context.Background(), testPreparedPass())
	if err != nil {
		t.Fatalf("detect: %v", err)
	}
	if response.Text != `{"elements":[]}` {
		t.Fatalf("text = %q", response.Text)
	}
	if !strings.Contains(response.RawText, "response.output_text.delta") {
		t.Fatalf("raw stream was not preserved: %q", response.RawText)
	}
}

func TestProviderChatCompletionsStreamExtractsDeltas(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/v1/chat/completions" {
			t.Fatalf("path = %s", r.URL.Path)
		}
		var payload map[string]any
		if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
			t.Fatalf("decode payload: %v", err)
		}
		if payload["stream"] != true {
			t.Fatalf("expected stream=true, got %#v", payload["stream"])
		}
		w.Header().Set("Content-Type", "text/event-stream")
		_, _ = w.Write([]byte("data: {\"choices\":[{\"delta\":{\"content\":\"{\\\"elements\\\":\"}}]}\n\n"))
		_, _ = w.Write([]byte("data: {\"choices\":[{\"delta\":{\"content\":\"[]}\"}}]}\n\n"))
		_, _ = w.Write([]byte("data: [DONE]\n\n"))
	}))
	defer srv.Close()

	client := newProviderClient(Options{
		WireAPI: "chat.completions",
		BaseURL: srv.URL,
		APIKey:  "test-key",
		Model:   "test-model",
		Timeout: time.Second,
		Stream:  true,
	})
	response, err := client.detect(context.Background(), testPreparedPass())
	if err != nil {
		t.Fatalf("detect: %v", err)
	}
	if response.Text != `{"elements":[]}` {
		t.Fatalf("text = %q", response.Text)
	}
}

func testPreparedPass() preparedPass {
	return preparedPass{
		Spec:   PassSpec{ID: "test"},
		Image:  image.NewRGBA(image.Rect(0, 0, 8, 8)),
		Prompt: "Return JSON.",
	}
}
