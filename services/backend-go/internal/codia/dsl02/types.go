package dsl02

type Document struct {
	Version string         `json:"version"`
	Kind    string         `json:"kind"`
	TaskID  string         `json:"taskId"`
	Page    Page           `json:"page"`
	Assets  []Asset        `json:"assets"`
	Root    Node           `json:"root"`
	Meta    map[string]any `json:"meta,omitempty"`
}

type Page struct {
	Name       string     `json:"name,omitempty"`
	Width      int        `json:"width"`
	Height     int        `json:"height"`
	Background Background `json:"background,omitempty"`
}

type Background struct {
	Type  string `json:"type"`
	Value string `json:"value"`
}

type Asset struct {
	AssetID string         `json:"assetId"`
	Type    string         `json:"type"`
	Role    string         `json:"role,omitempty"`
	URL     string         `json:"url"`
	Format  string         `json:"format"`
	Width   int            `json:"width,omitempty"`
	Height  int            `json:"height,omitempty"`
	Storage string         `json:"storage,omitempty"`
	Meta    map[string]any `json:"meta,omitempty"`
}

type Node struct {
	ID       string         `json:"id"`
	SchemaID string         `json:"schemaId,omitempty"`
	Role     string         `json:"role"`
	Type     string         `json:"type"`
	Name     string         `json:"name,omitempty"`
	BBox     BBox           `json:"bbox"`
	Style    map[string]any `json:"style,omitempty"`
	Text     *Text          `json:"text,omitempty"`
	Image    *Image         `json:"image,omitempty"`
	Children []Node         `json:"children,omitempty"`
	Meta     map[string]any `json:"meta,omitempty"`
}

type BBox struct {
	X      int `json:"x"`
	Y      int `json:"y"`
	Width  int `json:"width"`
	Height int `json:"height"`
}

type Text struct {
	Characters string `json:"characters"`
}

type Image struct {
	AssetID string `json:"assetId,omitempty"`
	URL     string `json:"url,omitempty"`
	Mode    string `json:"mode,omitempty"`
}
