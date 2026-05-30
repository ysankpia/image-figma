package server

import (
	"bytes"
	"context"
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

	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/compiler"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/detector"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/dsl02"
)

func TestCodiaPreviewUploadCompletesAndServesRuntimeDSL(t *testing.T) {
	tmp := t.TempDir()
	srv := NewWithCompiler(Config{StorageRoot: tmp}, func(options compiler.Options) (compiler.Result, error) {
		if options.InputPath == "" || options.OutputDir == "" || options.TaskID == "" {
			t.Fatalf("compile options missing required fields: %+v", options)
		}
		if err := os.MkdirAll(filepath.Join(options.OutputDir, dsl02.AssetDirName), 0o755); err != nil {
			return compiler.Result{}, err
		}
		if err := os.WriteFile(filepath.Join(options.OutputDir, dsl02.AssetDirName, "asset_cover.png"), makePNG(t), 0o644); err != nil {
			return compiler.Result{}, err
		}
		doc := dsl02.Document{
			Version: "0.2",
			Kind:    "codia_runtime",
			TaskID:  options.TaskID,
			Page:    dsl02.Page{Width: 160, Height: 120, Background: dsl02.Background{Type: "color", Value: "#FFFFFF"}},
			Assets: []dsl02.Asset{{
				AssetID: "asset_cover",
				Type:    "image",
				URL:     "assets/asset_cover.png",
				Format:  "png",
				Width:   160,
				Height:  120,
				Storage: "local",
			}},
			Root: dsl02.Node{
				ID:   "root",
				Role: "Root",
				Type: "frame",
				Name: "Root",
				BBox: dsl02.BBox{X: 0, Y: 0, Width: 160, Height: 120},
				Children: []dsl02.Node{{
					ID:    "cover",
					Role:  "ImageView",
					Type:  "image",
					Name:  "Image",
					BBox:  dsl02.BBox{X: 0, Y: 0, Width: 160, Height: 120},
					Image: &dsl02.Image{AssetID: "asset_cover", Mode: "fill"},
				}},
			},
		}
		if err := dsl02.WriteArtifact(options.OutputDir, doc); err != nil {
			return compiler.Result{}, err
		}
		return compiler.Result{Artifacts: compiler.Artifacts{RuntimeDSL02: dsl02.ArtifactName}}, nil
	})
	httpServer := httptest.NewServer(srv.Handler())
	defer httpServer.Close()

	uploadResp := postPNG(t, httpServer.URL+"/api/codia-preview", "input.png", makePNG(t))
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
	if !upload.Success || upload.Data.TaskID == "" || upload.Data.Stage != "codia_queued" {
		t.Fatalf("unexpected upload response: %+v", upload)
	}

	task := waitForCompletedTask(t, httpServer.URL, upload.Data.TaskID)
	if task.Stage != "codia_completed" {
		t.Fatalf("task stage = %q", task.Stage)
	}

	dslResp, err := http.Get(httpServer.URL + "/api/codia-preview/" + upload.Data.TaskID + "/dsl")
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
	if dslBody.Data.DSL.Version != "0.2" || dslBody.Data.DSL.Kind != "codia_runtime" || dslBody.Data.DSL.TaskID != upload.Data.TaskID {
		t.Fatalf("unexpected dsl body: %+v", dslBody.Data.DSL)
	}

	artifactsResp, err := http.Get(httpServer.URL + "/api/codia-preview/" + upload.Data.TaskID + "/artifacts")
	if err != nil {
		t.Fatalf("get artifacts: %v", err)
	}
	defer artifactsResp.Body.Close()
	if artifactsResp.StatusCode != http.StatusOK {
		t.Fatalf("artifacts status = %d body=%s", artifactsResp.StatusCode, readBody(t, artifactsResp))
	}

	assetResp, err := http.Get(httpServer.URL + "/api/codia-preview/" + upload.Data.TaskID + "/assets/asset_cover.png")
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

func TestCodiaPreviewRejectsNonPNG(t *testing.T) {
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
	req, err := http.NewRequest(http.MethodPost, srv.URL+"/api/codia-preview", &body)
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

func TestCodiaPreviewRunsDetectorWhenEnabled(t *testing.T) {
	tmp := t.TempDir()
	compileSawDetector := false
	srv := NewWithCompilerAndDetector(
		Config{StorageRoot: tmp, DetectorEnabled: true},
		func(options compiler.Options) (compiler.Result, error) {
			if options.DetectorCandidates == "" {
				t.Fatalf("expected detector candidates path")
			}
			if _, err := os.Stat(options.DetectorCandidates); err != nil {
				t.Fatalf("detector candidates missing: %v", err)
			}
			compileSawDetector = true
			if err := os.MkdirAll(options.OutputDir, 0o755); err != nil {
				return compiler.Result{}, err
			}
			doc := dsl02.Document{
				Version: "0.2",
				Kind:    "codia_runtime",
				TaskID:  options.TaskID,
				Page:    dsl02.Page{Width: 160, Height: 120, Background: dsl02.Background{Type: "color", Value: "#FFFFFF"}},
				Assets:  []dsl02.Asset{},
				Root: dsl02.Node{
					ID:   "root",
					Role: "Root",
					Type: "frame",
					Name: "Root",
					BBox: dsl02.BBox{X: 0, Y: 0, Width: 160, Height: 120},
				},
			}
			if err := dsl02.WriteArtifact(options.OutputDir, doc); err != nil {
				return compiler.Result{}, err
			}
			return compiler.Result{Artifacts: compiler.Artifacts{RuntimeDSL02: dsl02.ArtifactName}}, nil
		},
		func(_ context.Context, options detector.Options) (detector.RunResult, error) {
			if options.InputPath == "" || options.OutputDir == "" {
				t.Fatalf("detector options missing paths: %+v", options)
			}
			if err := os.MkdirAll(options.OutputDir, 0o755); err != nil {
				return detector.RunResult{}, err
			}
			data := []byte(`{"version":"ui_detector_candidates.v1","image":{"path":"input.png","width":160,"height":120},"provider":{"name":"test","wireApi":"test","model":"test"},"preprocess":{"passes":[]},"candidates":[],"summary":{"total":0,"roleCounts":{}}}`)
			if err := os.WriteFile(filepath.Join(options.OutputDir, "ui_detector_candidates.v1.json"), data, 0o644); err != nil {
				return detector.RunResult{}, err
			}
			return detector.RunResult{}, nil
		},
	)
	httpServer := httptest.NewServer(srv.Handler())
	defer httpServer.Close()

	uploadResp := postPNG(t, httpServer.URL+"/api/codia-preview", "input.png", makePNG(t))
	if uploadResp.StatusCode != http.StatusOK {
		t.Fatalf("upload status = %d body=%s", uploadResp.StatusCode, readBody(t, uploadResp))
	}
	var upload struct {
		Data struct {
			TaskID string `json:"taskId"`
		} `json:"data"`
	}
	decodeResponse(t, uploadResp, &upload)
	task := waitForCompletedTask(t, httpServer.URL, upload.Data.TaskID)
	if task.Status != "completed" {
		t.Fatalf("task status = %q message=%s", task.Status, task.Message)
	}
	if !compileSawDetector {
		t.Fatalf("compile did not receive detector candidates")
	}
}

func TestCodiaPreviewFallsBackWhenDetectorFails(t *testing.T) {
	tmp := t.TempDir()
	compileCalled := false
	srv := NewWithCompilerAndDetector(
		Config{StorageRoot: tmp, DetectorEnabled: true},
		func(options compiler.Options) (compiler.Result, error) {
			if options.DetectorCandidates != "" {
				t.Fatalf("expected no detector candidates after fallback, got %q", options.DetectorCandidates)
			}
			compileCalled = true
			return writeMinimalRuntimeDSL(options)
		},
		func(_ context.Context, _ detector.Options) (detector.RunResult, error) {
			return detector.RunResult{}, errors.New(`pass imageview: Post "https://aicode.cat/v1/responses": local error: tls: bad record MAC`)
		},
	)
	httpServer := httptest.NewServer(srv.Handler())
	defer httpServer.Close()

	uploadResp := postPNG(t, httpServer.URL+"/api/codia-preview", "input.png", makePNG(t))
	if uploadResp.StatusCode != http.StatusOK {
		t.Fatalf("upload status = %d body=%s", uploadResp.StatusCode, readBody(t, uploadResp))
	}
	var upload struct {
		Data struct {
			TaskID string `json:"taskId"`
		} `json:"data"`
	}
	decodeResponse(t, uploadResp, &upload)
	task := waitForCompletedTask(t, httpServer.URL, upload.Data.TaskID)
	if task.Status != "completed" {
		t.Fatalf("task status = %q message=%s", task.Status, task.Message)
	}
	if !compileCalled {
		t.Fatalf("compile was not called after detector fallback")
	}
	if len(task.Warnings) != 1 || task.Warnings[0].Code != "CODIA_DETECTOR_FALLBACK" {
		t.Fatalf("warnings = %+v", task.Warnings)
	}
	fallbackPath := filepath.Join(tmp, "codia_previews", upload.Data.TaskID, "compile", "detector", "detector_fallback.v1.json")
	if _, err := os.Stat(fallbackPath); err != nil {
		t.Fatalf("expected detector fallback artifact: %v", err)
	}
}

func TestCodiaPreviewMarksTaskFailedOnPanic(t *testing.T) {
	srv := NewWithCompiler(Config{StorageRoot: t.TempDir()}, func(_ compiler.Options) (compiler.Result, error) {
		panic("synthetic compiler panic")
	})
	httpServer := httptest.NewServer(srv.Handler())
	defer httpServer.Close()

	uploadResp := postPNG(t, httpServer.URL+"/api/codia-preview", "input.png", makePNG(t))
	if uploadResp.StatusCode != http.StatusOK {
		t.Fatalf("upload status = %d body=%s", uploadResp.StatusCode, readBody(t, uploadResp))
	}
	var upload struct {
		Data struct {
			TaskID string `json:"taskId"`
		} `json:"data"`
	}
	decodeResponse(t, uploadResp, &upload)
	task := waitForCompletedTask(t, httpServer.URL, upload.Data.TaskID)
	if task.Status != "failed" || task.Stage != "codia_panic" {
		t.Fatalf("task = %+v", task)
	}
	if task.Error == nil || task.Error.Code != "CODIA_TASK_PANIC" {
		t.Fatalf("task error = %+v", task.Error)
	}
}

type publicTask struct {
	TaskID   string        `json:"taskId"`
	Status   string        `json:"status"`
	Stage    string        `json:"stage"`
	Progress int           `json:"progress"`
	Message  string        `json:"message"`
	Error    *TaskError    `json:"error,omitempty"`
	Warnings []TaskWarning `json:"warnings,omitempty"`
}

func waitForCompletedTask(t *testing.T, baseURL, taskID string) publicTask {
	t.Helper()
	deadline := time.Now().Add(2 * time.Second)
	for time.Now().Before(deadline) {
		resp, err := http.Get(baseURL + "/api/codia-preview/" + taskID)
		if err != nil {
			t.Fatalf("get task: %v", err)
		}
		var body struct {
			Success bool       `json:"success"`
			Data    publicTask `json:"data"`
		}
		decodeResponse(t, resp, &body)
		_ = resp.Body.Close()
		if body.Data.Status == "completed" || body.Data.Status == "failed" {
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

func writeMinimalRuntimeDSL(options compiler.Options) (compiler.Result, error) {
	if err := os.MkdirAll(options.OutputDir, 0o755); err != nil {
		return compiler.Result{}, err
	}
	doc := dsl02.Document{
		Version: "0.2",
		Kind:    "codia_runtime",
		TaskID:  options.TaskID,
		Page:    dsl02.Page{Width: 160, Height: 120, Background: dsl02.Background{Type: "color", Value: "#FFFFFF"}},
		Assets:  []dsl02.Asset{},
		Root: dsl02.Node{
			ID:   "root",
			Role: "Root",
			Type: "frame",
			Name: "Root",
			BBox: dsl02.BBox{X: 0, Y: 0, Width: 160, Height: 120},
		},
	}
	if err := dsl02.WriteArtifact(options.OutputDir, doc); err != nil {
		return compiler.Result{}, err
	}
	return compiler.Result{Artifacts: compiler.Artifacts{RuntimeDSL02: dsl02.ArtifactName}}, nil
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
