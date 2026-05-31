package exportdsl

import "github.com/luqing-studio/image-figma/services/backend-go/internal/image/geometry"

const (
	Version = "1.0"
	Kind    = "draft_runtime"
)

type Document struct {
	Version string         `json:"version"`
	Kind    string         `json:"kind"`
	TaskID  string         `json:"taskId"`
	Page    Page           `json:"page"`
	Assets  []Asset        `json:"assets,omitempty"`
	Root    Node           `json:"root"`
	Meta    map[string]any `json:"meta,omitempty"`
}

type Page struct {
	Name       string `json:"name,omitempty"`
	Width      int    `json:"width"`
	Height     int    `json:"height"`
	Background string `json:"background,omitempty"`
}

type Asset struct {
	AssetID string         `json:"assetId"`
	Type    string         `json:"type"`
	URL     string         `json:"url,omitempty"`
	Path    string         `json:"path,omitempty"`
	Format  string         `json:"format,omitempty"`
	Width   int            `json:"width,omitempty"`
	Height  int            `json:"height,omitempty"`
	Meta    map[string]any `json:"meta,omitempty"`
}

type Node struct {
	ID       string         `json:"id"`
	Type     string         `json:"type"`
	Name     string         `json:"name,omitempty"`
	BBox     geometry.Rect  `json:"bbox"`
	Z        int            `json:"z,omitempty"`
	Visible  *bool          `json:"visible,omitempty"`
	Style    map[string]any `json:"style,omitempty"`
	Text     *Text          `json:"text,omitempty"`
	Image    *Image         `json:"image,omitempty"`
	Children []Node         `json:"children,omitempty"`
	Meta     map[string]any `json:"meta,omitempty"`
}

type Text struct {
	Characters string `json:"characters"`
}

type Image struct {
	AssetID string `json:"assetId"`
	Mode    string `json:"mode,omitempty"`
}
