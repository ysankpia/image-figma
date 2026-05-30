package canvasexport

import "github.com/luqing-studio/image-figma/services/backend-go/internal/codia/canvas"

const (
	ReportArtifactName = "codia_canvas_export_report.md"
	CanvasArtifactName = "codia_canvas_like.v1.canvas.json"
)

type Document struct {
	Version int               `json:"version"`
	Root    canvas.CanvasNode `json:"root"`
	Blobs   map[string]any    `json:"blobs"`
}

type Result struct {
	Document Document `json:"-"`
	Report   Report   `json:"report"`
}

type Report struct {
	SchemaName       string   `json:"schemaName"`
	Version          string   `json:"version"`
	NodeCount        int      `json:"nodeCount"`
	CanvasVersion    int      `json:"canvasVersion"`
	DesignFrameName  string   `json:"designFrameName"`
	RootName         string   `json:"rootName"`
	UnsupportedNotes []string `json:"unsupportedNotes"`
}
