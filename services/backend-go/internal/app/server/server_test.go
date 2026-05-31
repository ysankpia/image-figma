package server

import (
	"bytes"
	"encoding/json"
	"errors"
	"image"
	"image/color"
	"image/png"
	"io"
	"mime/multipart"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"
	"time"

	apptask "github.com/luqing-studio/image-figma/services/backend-go/internal/app/task"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/draft/compile"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/draft/exportdsl"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/image/geometry"
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

func TestDraftPreviewUploadCompletesAndServesRuntimeDSL(t *testing.T) {
	tmp := t.TempDir()
	srv := NewWithCompiler(Config{StorageRoot: tmp, OCRProvider: "test-ocr"}, func(options compile.Options) (compile.Result, error) {
		if options.InputPath == "" || options.OutputDir == "" || options.TaskID == "" {
			t.Fatalf("compile options missing required fields: %+v", options)
		}
		if options.OCRProvider != "test-ocr" {
			t.Fatalf("ocr provider = %q", options.OCRProvider)
		}
		return writeMinimalDraftRuntime(options)
	})
	httpServer := httptest.NewServer(srv.Handler())
	defer httpServer.Close()

	uploadResp := postPNG(t, httpServer.URL+"/api/draft-preview", "input.png", makePNG(t))
	if uploadResp.StatusCode != http.StatusOK {
		t.Fatalf("upload status = %d body=%s", uploadResp.StatusCode, readBody(t, uploadResp))
	}
	var upload struct {
		Success bool `json:"success"`
		Data    struct {
			TaskID string `json:"taskId"`
			Status string `json:"status"`
			Stage  string `json:"stage"`
		} `json:"data"`
	}
	decodeResponse(t, uploadResp, &upload)
	if !upload.Success || upload.Data.TaskID == "" || upload.Data.Status != string(apptask.StatusQueued) || upload.Data.Stage != string(apptask.StageDraftQueued) {
		t.Fatalf("unexpected upload response: %+v", upload)
	}

	task := waitForTerminalTask(t, httpServer.URL, upload.Data.TaskID)
	if task.Status != string(apptask.StatusCompleted) || task.Stage != string(apptask.StageDraftCompleted) {
		t.Fatalf("task = %+v", task)
	}

	dslResp, err := http.Get(httpServer.URL + "/api/draft-preview/" + upload.Data.TaskID + "/dsl")
	if err != nil {
		t.Fatalf("get dsl: %v", err)
	}
	defer dslResp.Body.Close()
	if dslResp.StatusCode != http.StatusOK {
		t.Fatalf("dsl status = %d body=%s", dslResp.StatusCode, readBody(t, dslResp))
	}
	var dslBody struct {
		Success bool `json:"success"`
		Data    struct {
			DSL struct {
				Version string `json:"version"`
				Kind    string `json:"kind"`
				TaskID  string `json:"taskId"`
			} `json:"dsl"`
		} `json:"data"`
	}
	decodeResponse(t, dslResp, &dslBody)
	if dslBody.Data.DSL.Version != exportdsl.Version || dslBody.Data.DSL.Kind != exportdsl.Kind || dslBody.Data.DSL.TaskID != upload.Data.TaskID {
		t.Fatalf("unexpected dsl body: %+v", dslBody.Data.DSL)
	}

	artifactsResp, err := http.Get(httpServer.URL + "/api/draft-preview/" + upload.Data.TaskID + "/artifacts")
	if err != nil {
		t.Fatalf("get artifacts: %v", err)
	}
	defer artifactsResp.Body.Close()
	if artifactsResp.StatusCode != http.StatusOK {
		t.Fatalf("artifacts status = %d body=%s", artifactsResp.StatusCode, readBody(t, artifactsResp))
	}

	assetResp, err := http.Get(httpServer.URL + "/api/draft-preview/" + upload.Data.TaskID + "/assets/asset_cover.png")
	if err != nil {
		t.Fatalf("get asset: %v", err)
	}
	defer assetResp.Body.Close()
	if assetResp.StatusCode != http.StatusOK {
		t.Fatalf("asset status = %d body=%s", assetResp.StatusCode, readBody(t, assetResp))
	}
	if contentType := assetResp.Header.Get("Content-Type"); contentType != "image/png" {
		t.Fatalf("asset content-type = %q", contentType)
	}
}

func TestDraftPreviewRejectsNonPNG(t *testing.T) {
	srv := httptest.NewServer(NewWithCompiler(Config{StorageRoot: t.TempDir()}, nil).Handler())
	defer srv.Close()

	var body bytes.Buffer
	writer := multipart.NewWriter(&body)
	part, err := writer.CreateFormFile("file", "input.txt")
	if err != nil {
		t.Fatalf("create form file: %v", err)
	}
	if _, err := part.Write([]byte("not png")); err != nil {
		t.Fatalf("write form: %v", err)
	}
	if err := writer.Close(); err != nil {
		t.Fatalf("close form: %v", err)
	}
	req, err := http.NewRequest(http.MethodPost, srv.URL+"/api/draft-preview", &body)
	if err != nil {
		t.Fatalf("new request: %v", err)
	}
	req.Header.Set("Content-Type", writer.FormDataContentType())
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("post: %v", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusBadRequest {
		t.Fatalf("status = %d body=%s", resp.StatusCode, readBody(t, resp))
	}
}

func TestDraftPreviewReportsCompileFailure(t *testing.T) {
	srv := httptest.NewServer(NewWithCompiler(Config{StorageRoot: t.TempDir()}, func(compile.Options) (compile.Result, error) {
		return compile.Result{}, errors.New("compile failed")
	}).Handler())
	defer srv.Close()

	uploadResp := postPNG(t, srv.URL+"/api/draft-preview", "input.png", makePNG(t))
	if uploadResp.StatusCode != http.StatusOK {
		t.Fatalf("upload status = %d body=%s", uploadResp.StatusCode, readBody(t, uploadResp))
	}
	var upload struct {
		Data struct {
			TaskID string `json:"taskId"`
		} `json:"data"`
	}
	decodeResponse(t, uploadResp, &upload)
	task := waitForTerminalTask(t, srv.URL, upload.Data.TaskID)
	if task.Status != string(apptask.StatusFailed) || task.Stage != string(apptask.StageDraftFailed) {
		t.Fatalf("task = %+v", task)
	}
	if task.Error == nil || task.Error.Code != "DRAFT_COMPILE_FAILED" {
		t.Fatalf("task error = %+v", task.Error)
	}
}

func TestDraftPreviewRecoversCompilePanic(t *testing.T) {
	srv := httptest.NewServer(NewWithCompiler(Config{StorageRoot: t.TempDir()}, func(compile.Options) (compile.Result, error) {
		panic("boom")
	}).Handler())
	defer srv.Close()

	uploadResp := postPNG(t, srv.URL+"/api/draft-preview", "input.png", makePNG(t))
	if uploadResp.StatusCode != http.StatusOK {
		t.Fatalf("upload status = %d body=%s", uploadResp.StatusCode, readBody(t, uploadResp))
	}
	var upload struct {
		Data struct {
			TaskID string `json:"taskId"`
		} `json:"data"`
	}
	decodeResponse(t, uploadResp, &upload)
	task := waitForTerminalTask(t, srv.URL, upload.Data.TaskID)
	if task.Status != string(apptask.StatusFailed) || task.Stage != string(apptask.StageDraftPanic) {
		t.Fatalf("task = %+v", task)
	}
	if task.Error == nil || task.Error.Code != "DRAFT_TASK_PANIC" {
		t.Fatalf("task error = %+v", task.Error)
	}
}

type publicTask struct {
	TaskID   string            `json:"taskId"`
	Status   string            `json:"status"`
	Stage    string            `json:"stage"`
	Progress int               `json:"progress"`
	Message  string            `json:"message"`
	Error    *apptask.Error    `json:"error,omitempty"`
	Warnings []apptask.Warning `json:"warnings,omitempty"`
}

func waitForTerminalTask(t *testing.T, baseURL, taskID string) publicTask {
	t.Helper()
	deadline := time.Now().Add(2 * time.Second)
	for time.Now().Before(deadline) {
		resp, err := http.Get(baseURL + "/api/draft-preview/" + taskID)
		if err != nil {
			t.Fatalf("get task: %v", err)
		}
		var body struct {
			Success bool       `json:"success"`
			Data    publicTask `json:"data"`
		}
		decodeResponse(t, resp, &body)
		if body.Data.Status == string(apptask.StatusCompleted) || body.Data.Status == string(apptask.StatusFailed) {
			return body.Data
		}
		time.Sleep(10 * time.Millisecond)
	}
	t.Fatalf("task %s did not complete", taskID)
	return publicTask{}
}

func postPNG(t *testing.T, url, name string, data []byte) *http.Response {
	t.Helper()
	var body bytes.Buffer
	writer := multipart.NewWriter(&body)
	part, err := writer.CreateFormFile("file", name)
	if err != nil {
		t.Fatalf("create form file: %v", err)
	}
	if _, err := part.Write(data); err != nil {
		t.Fatalf("write png: %v", err)
	}
	if err := writer.Close(); err != nil {
		t.Fatalf("close multipart: %v", err)
	}
	req, err := http.NewRequest(http.MethodPost, url, &body)
	if err != nil {
		t.Fatalf("new request: %v", err)
	}
	req.Header.Set("Content-Type", writer.FormDataContentType())
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("post png: %v", err)
	}
	return resp
}

func makePNG(t *testing.T) []byte {
	t.Helper()
	img := image.NewRGBA(image.Rect(0, 0, 160, 120))
	for y := 0; y < 120; y++ {
		for x := 0; x < 160; x++ {
			img.Set(x, y, color.RGBA{R: 245, G: 245, B: 245, A: 255})
		}
	}
	var buf bytes.Buffer
	if err := png.Encode(&buf, img); err != nil {
		t.Fatalf("encode png: %v", err)
	}
	return buf.Bytes()
}

func writeMinimalDraftRuntime(options compile.Options) (compile.Result, error) {
	if err := os.MkdirAll(filepath.Join(options.OutputDir, "assets"), 0o755); err != nil {
		return compile.Result{}, err
	}
	if err := os.WriteFile(filepath.Join(options.OutputDir, "assets", "asset_cover.png"), makePNGForWrite(), 0o644); err != nil {
		return compile.Result{}, err
	}
	doc := exportdsl.Document{
		Version: exportdsl.Version,
		Kind:    exportdsl.Kind,
		TaskID:  options.TaskID,
		Page: exportdsl.Page{
			Name:   "Draft",
			Width:  160,
			Height: 120,
		},
		Assets: []exportdsl.Asset{{
			AssetID: "asset_cover",
			Type:    "image",
			URL:     "assets/asset_cover.png",
			Format:  "png",
			Width:   160,
			Height:  120,
		}},
		Root: exportdsl.Node{
			ID:   "root",
			Type: "frame",
			Name: "Draft",
			BBox: geometry.Rect{Width: 160, Height: 120},
			Children: []exportdsl.Node{{
				ID:    "cover",
				Type:  "image",
				Name:  "Cover",
				BBox:  geometry.Rect{Width: 160, Height: 120},
				Image: &exportdsl.Image{AssetID: "asset_cover", Mode: "fill"},
			}},
		},
	}
	if err := exportdsl.WriteArtifact(filepath.Join(options.OutputDir, "draft"), doc); err != nil {
		return compile.Result{}, err
	}
	return compile.Result{
		DSL: doc,
		Artifacts: compile.Artifacts{
			EditableLayerGraph: "draft/editable_layer_graph.v1.json",
			ValidationReport:   "draft/draft_validation_report.md",
			AssetManifest:      "assets/asset_manifest.json",
			RuntimeDSL:         "draft/" + exportdsl.ArtifactName,
		},
	}, nil
}

func makePNGForWrite() []byte {
	img := image.NewRGBA(image.Rect(0, 0, 2, 2))
	var buf bytes.Buffer
	_ = png.Encode(&buf, img)
	return buf.Bytes()
}

func decodeResponse(t *testing.T, resp *http.Response, out any) {
	t.Helper()
	defer resp.Body.Close()
	if err := json.NewDecoder(resp.Body).Decode(out); err != nil {
		t.Fatalf("decode response: %v", err)
	}
}

func readBody(t *testing.T, resp *http.Response) string {
	t.Helper()
	data, err := io.ReadAll(resp.Body)
	if err != nil {
		t.Fatalf("read body: %v", err)
	}
	return string(data)
}
