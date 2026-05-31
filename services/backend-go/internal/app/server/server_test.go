package server

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestHealth(t *testing.T) {
	srv := httptest.NewServer(New(Config{}).Handler())
	defer srv.Close()

	resp, err := http.Get(srv.URL + "/api/health")
	if err != nil {
		t.Fatalf("get health: %v", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("status = %d", resp.StatusCode)
	}
	var body struct {
		Success bool `json:"success"`
		Data    struct {
			Status  string `json:"status"`
			Version string `json:"version"`
		} `json:"data"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&body); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if !body.Success || body.Data.Status != "ok" || body.Data.Version != "draft-server-v0.1" {
		t.Fatalf("unexpected health body: %+v", body)
	}
}

func TestDraftPreviewRouteIsReserved(t *testing.T) {
	srv := httptest.NewServer(New(Config{}).Handler())
	defer srv.Close()

	resp, err := http.Post(srv.URL+"/api/draft-preview", "image/png", nil)
	if err != nil {
		t.Fatalf("post draft preview: %v", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusNotImplemented {
		t.Fatalf("status = %d", resp.StatusCode)
	}
	var body struct {
		Success bool `json:"success"`
		Error   struct {
			Code string `json:"code"`
		} `json:"error"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&body); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if body.Success || body.Error.Code != "DRAFT_PIPELINE_NOT_IMPLEMENTED" {
		t.Fatalf("unexpected body: %+v", body)
	}
}
