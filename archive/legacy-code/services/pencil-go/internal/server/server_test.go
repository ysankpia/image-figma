package server

import (
	"bytes"
	"encoding/json"
	"image"
	"image/color"
	"image/draw"
	"image/png"
	"io"
	"mime/multipart"
	"net/http"
	"net/http/httptest"
	"net/textproto"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func TestProjectUploadCompletesAndServesManifestAndZip(t *testing.T) {
	tmp := t.TempDir()
	handler := New(Config{StorageRoot: tmp, OCRProvider: "none", MaxUploadBytes: 2 * 1024 * 1024, MaxFiles: 3}).Handler()
	pngBytes := makeServerPNG(t)

	taskID := postPencilProject(t, handler, []uploadPart{{name: "screen.png", data: pngBytes, contentType: "image/png"}})
	task := waitForCompletedTask(t, handler, taskID)
	if task.Status != StatusCompleted {
		t.Fatalf("task did not complete: %#v", task)
	}
	if task.PageCount != 1 {
		t.Fatalf("page count = %d", task.PageCount)
	}
	if task.DownloadURL != "/api/pencil/projects/"+taskID+"/download.zip" {
		t.Fatalf("download URL = %q", task.DownloadURL)
	}
	assertServerFileExists(t, filepath.Join(tmp, "projects", taskID, "task.json"))

	manifestReq := httptest.NewRequest(http.MethodGet, "/api/pencil/projects/"+taskID+"/manifest", nil)
	manifestRes := httptest.NewRecorder()
	handler.ServeHTTP(manifestRes, manifestReq)
	if manifestRes.Code != http.StatusOK {
		t.Fatalf("manifest status = %d body=%s", manifestRes.Code, manifestRes.Body.String())
	}

	zipReq := httptest.NewRequest(http.MethodGet, "/api/pencil/projects/"+taskID+"/download.zip", nil)
	zipRes := httptest.NewRecorder()
	handler.ServeHTTP(zipRes, zipReq)
	if zipRes.Code != http.StatusOK {
		t.Fatalf("zip status = %d body=%s", zipRes.Code, zipRes.Body.String())
	}
	if !bytes.HasPrefix(zipRes.Body.Bytes(), []byte("PK")) {
		t.Fatalf("download is not a zip")
	}
}

func TestProjectUploadRejectsNonPNG(t *testing.T) {
	handler := New(Config{StorageRoot: t.TempDir(), OCRProvider: "none", MaxUploadBytes: 1024, MaxFiles: 3}).Handler()
	body, contentType := multipartBody(t, []uploadPart{{name: "not-image.txt", data: []byte("hello"), contentType: "text/plain"}})
	req := httptest.NewRequest(http.MethodPost, "/api/pencil/projects", body)
	req.Header.Set("Content-Type", contentType)
	res := httptest.NewRecorder()
	handler.ServeHTTP(res, req)
	if res.Code != http.StatusBadRequest {
		t.Fatalf("status = %d body=%s", res.Code, res.Body.String())
	}
	if !strings.Contains(res.Body.String(), "not a PNG") {
		t.Fatalf("expected PNG rejection, got %s", res.Body.String())
	}
}

type uploadPart struct {
	name        string
	data        []byte
	contentType string
}

func postPencilProject(t *testing.T, handler http.Handler, files []uploadPart) string {
	t.Helper()
	body, contentType := multipartBody(t, files)
	req := httptest.NewRequest(http.MethodPost, "/api/pencil/projects", body)
	req.Header.Set("Content-Type", contentType)
	res := httptest.NewRecorder()
	handler.ServeHTTP(res, req)
	if res.Code != http.StatusOK {
		t.Fatalf("post status = %d body=%s", res.Code, res.Body.String())
	}
	var payload struct {
		Success bool `json:"success"`
		Data    struct {
			TaskID string `json:"taskId"`
		} `json:"data"`
	}
	if err := json.Unmarshal(res.Body.Bytes(), &payload); err != nil {
		t.Fatal(err)
	}
	if !payload.Success || payload.Data.TaskID == "" {
		t.Fatalf("unexpected response: %s", res.Body.String())
	}
	return payload.Data.TaskID
}

func multipartBody(t *testing.T, files []uploadPart) (io.Reader, string) {
	t.Helper()
	var body bytes.Buffer
	writer := multipart.NewWriter(&body)
	for _, file := range files {
		header := make(textproto.MIMEHeader)
		header.Set("Content-Disposition", `form-data; name="files[]"; filename="`+file.name+`"`)
		header.Set("Content-Type", file.contentType)
		part, err := writer.CreatePart(header)
		if err != nil {
			t.Fatal(err)
		}
		if _, err := part.Write(file.data); err != nil {
			t.Fatal(err)
		}
	}
	field, err := writer.CreateFormField("includeDebug")
	if err != nil {
		t.Fatal(err)
	}
	if _, err := field.Write([]byte("false")); err != nil {
		t.Fatal(err)
	}
	if err := writer.Close(); err != nil {
		t.Fatal(err)
	}
	return &body, writer.FormDataContentType()
}

func waitForCompletedTask(t *testing.T, handler http.Handler, taskID string) Task {
	t.Helper()
	deadline := time.Now().Add(5 * time.Second)
	for time.Now().Before(deadline) {
		req := httptest.NewRequest(http.MethodGet, "/api/pencil/projects/"+taskID, nil)
		res := httptest.NewRecorder()
		handler.ServeHTTP(res, req)
		if res.Code != http.StatusOK {
			t.Fatalf("get status = %d body=%s", res.Code, res.Body.String())
		}
		var payload struct {
			Success bool `json:"success"`
			Data    Task `json:"data"`
		}
		if err := json.Unmarshal(res.Body.Bytes(), &payload); err != nil {
			t.Fatal(err)
		}
		if payload.Data.Status == StatusCompleted {
			return payload.Data
		}
		if payload.Data.Status == StatusFailed {
			t.Fatalf("task failed: %#v", payload.Data)
		}
		time.Sleep(25 * time.Millisecond)
	}
	t.Fatalf("task %s did not complete", taskID)
	return Task{}
}

func makeServerPNG(t *testing.T) []byte {
	t.Helper()
	img := image.NewRGBA(image.Rect(0, 0, 120, 160))
	draw.Draw(img, img.Bounds(), &image.Uniform{C: color.RGBA{R: 244, G: 246, B: 248, A: 255}}, image.Point{}, draw.Src)
	draw.Draw(img, image.Rect(18, 22, 102, 62), &image.Uniform{C: color.RGBA{R: 36, G: 112, B: 224, A: 255}}, image.Point{}, draw.Src)
	draw.Draw(img, image.Rect(22, 92, 98, 134), &image.Uniform{C: color.RGBA{R: 25, G: 30, B: 38, A: 255}}, image.Point{}, draw.Src)
	var buf bytes.Buffer
	if err := png.Encode(&buf, img); err != nil {
		t.Fatal(err)
	}
	return buf.Bytes()
}

func assertServerFileExists(t *testing.T, path string) {
	t.Helper()
	if _, err := os.Stat(path); err != nil {
		t.Fatalf("expected %s: %v", path, err)
	}
}
