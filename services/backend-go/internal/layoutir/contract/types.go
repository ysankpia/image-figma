package contract

import "github.com/luqing-studio/image-figma/services/backend-go/internal/image/geometry"

const Version = "ui_layout_ir.v1"

type NodeType string

const (
	NodePage        NodeType = "page"
	NodeSection     NodeType = "section"
	NodeRow         NodeType = "row"
	NodeColumn      NodeType = "column"
	NodeGroup       NodeType = "group"
	NodeOverlay     NodeType = "overlay"
	NodeText        NodeType = "text"
	NodeImage       NodeType = "image"
	NodeShape       NodeType = "shape"
	NodeIcon        NodeType = "icon"
	NodeUnknownCrop NodeType = "unknown_crop"
)

type LayoutMode string

const (
	LayoutAbsolute LayoutMode = "absolute"
	LayoutRow      LayoutMode = "row"
	LayoutColumn   LayoutMode = "column"
	LayoutOverlay  LayoutMode = "overlay"
)

type DecisionState string

const (
	DecisionEmit          DecisionState = "emit"
	DecisionGroup         DecisionState = "group"
	DecisionSplit         DecisionState = "split"
	DecisionMerge         DecisionState = "merge"
	DecisionSuppress      DecisionState = "suppress"
	DecisionFallbackCrop  DecisionState = "fallback_crop"
	DecisionPromoteText   DecisionState = "promote_text"
	DecisionPromoteImage  DecisionState = "promote_image"
	DecisionReferenceOnly DecisionState = "reference_only"
)

type Document struct {
	Version     string     `json:"version"`
	SourceImage ImageMeta  `json:"sourceImage"`
	Root        Node       `json:"root"`
	Assets      []Asset    `json:"assets,omitempty"`
	Evidence    []Evidence `json:"evidence,omitempty"`
	Decisions   []Decision `json:"decisions,omitempty"`
	Summary     Summary    `json:"summary"`
}

type ImageMeta struct {
	Path   string `json:"path,omitempty"`
	Width  int    `json:"width"`
	Height int    `json:"height"`
	SHA256 string `json:"sha256,omitempty"`
}

type Node struct {
	ID             string            `json:"id"`
	Type           NodeType          `json:"type"`
	Name           string            `json:"name,omitempty"`
	BBox           geometry.Rect     `json:"bbox"`
	Layout         Layout            `json:"layout"`
	Style          Style             `json:"style,omitempty"`
	Children       []Node            `json:"children,omitempty"`
	SourceRefs     []SourceRef       `json:"sourceRefs,omitempty"`
	Confidence     float64           `json:"confidence,omitempty"`
	FallbackPolicy string            `json:"fallbackPolicy,omitempty"`
	SemanticTags   []string          `json:"semanticTags,omitempty"`
	Text           *Text             `json:"text,omitempty"`
	AssetRef       *AssetRef         `json:"assetRef,omitempty"`
	Meta           map[string]string `json:"meta,omitempty"`
}

type Layout struct {
	Mode    LayoutMode `json:"mode"`
	Gap     int        `json:"gap,omitempty"`
	Padding Insets     `json:"padding,omitempty"`
	Align   string     `json:"align,omitempty"`
	Justify string     `json:"justify,omitempty"`
}

type Insets struct {
	Top    int `json:"top,omitempty"`
	Right  int `json:"right,omitempty"`
	Bottom int `json:"bottom,omitempty"`
	Left   int `json:"left,omitempty"`
}

type Style struct {
	Fill         string  `json:"fill,omitempty"`
	Stroke       string  `json:"stroke,omitempty"`
	Opacity      float64 `json:"opacity,omitempty"`
	CornerRadius float64 `json:"cornerRadius,omitempty"`
}

type Text struct {
	Characters string `json:"characters"`
}

type AssetRef struct {
	AssetID string `json:"assetId"`
}

type Asset struct {
	ID         string        `json:"id"`
	Type       string        `json:"type"`
	Path       string        `json:"path,omitempty"`
	URL        string        `json:"url,omitempty"`
	Format     string        `json:"format,omitempty"`
	BBox       geometry.Rect `json:"bbox,omitempty"`
	Width      int           `json:"width,omitempty"`
	Height     int           `json:"height,omitempty"`
	SourceRefs []SourceRef   `json:"sourceRefs,omitempty"`
}

type Evidence struct {
	ID         string            `json:"id"`
	Kind       string            `json:"kind"`
	RoleHint   string            `json:"roleHint,omitempty"`
	BBox       geometry.Rect     `json:"bbox,omitempty"`
	Source     string            `json:"source,omitempty"`
	Confidence float64           `json:"confidence,omitempty"`
	SourceRefs []SourceRef       `json:"sourceRefs,omitempty"`
	Meta       map[string]string `json:"meta,omitempty"`
}

type Decision struct {
	ID         string        `json:"id"`
	State      DecisionState `json:"state"`
	NodeID     string        `json:"nodeId,omitempty"`
	Reason     string        `json:"reason"`
	SourceRefs []SourceRef   `json:"sourceRefs,omitempty"`
	Score      float64       `json:"score,omitempty"`
}

type SourceRef struct {
	Kind string `json:"kind"`
	ID   string `json:"id"`
	Role string `json:"role,omitempty"`
}

type Summary struct {
	NodeCount     int            `json:"nodeCount"`
	AssetCount    int            `json:"assetCount"`
	EvidenceCount int            `json:"evidenceCount"`
	DecisionCount int            `json:"decisionCount"`
	TypeCounts    map[string]int `json:"typeCounts,omitempty"`
}
