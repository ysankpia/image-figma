package server

import (
	"bytes"
	"encoding/json"
	"image"
	"image/color"
	"image/png"
	"io"
	"mime/multipart"
	"net/http"
	"net/http/httptest"
	"os"
	"testing"
	"time"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/compiler"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/dsl02"
)

func TestCodiaPreviewUploadCompletesAndServesRuntimeDSL(t *testing.T) {
	tmp := t.TempDir()
	srv := NewWithCompiler(Config{StorageRoot: tmp}, func(options compiler.Options) (compiler.Result, error) {
		if options.InputPath == "" || options.OutputDir == "" || options.TaskID == "" {
			t.Fatalf("compile options missing required fields: %+v", options)
		}
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

type publicTask struct {
	TaskID   string `json:"taskId"`
	Status   string `json:"status"`
	Stage    string `json:"stage"`
	Progress int    `json:"progress"`
	Message  string `json:"message"`
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
