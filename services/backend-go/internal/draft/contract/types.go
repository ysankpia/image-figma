package contract

import "github.com/luqing-studio/image-figma/services/backend-go/internal/image/geometry"

const Version = "editable_layer_graph.v1"

type LayerKind string

const (
	LayerPage           LayerKind = "Page"
	LayerReferenceImage LayerKind = "ReferenceImage"
	LayerText           LayerKind = "TextLayer"
	LayerRaster         LayerKind = "RasterLayer"
	LayerShape          LayerKind = "ShapeLayer"
	LayerGroup          LayerKind = "GroupLayer"
)

type DecisionState string

const (
	DecisionEmit          DecisionState = "emit"
	DecisionConsume       DecisionState = "consume"
	DecisionSuppress      DecisionState = "suppress"
	DecisionRefine        DecisionState = "refine"
	DecisionHint          DecisionState = "hint"
	DecisionReferenceOnly DecisionState = "reference_only"
)

type BBoxAuthority string

const (
	BBoxAuthoritySourceImage   BBoxAuthority = "source_image"
	BBoxAuthorityM29           BBoxAuthority = "m29"
	BBoxAuthorityOCR           BBoxAuthority = "ocr"
	BBoxAuthorityVision        BBoxAuthority = "vision"
	BBoxAuthorityReview        BBoxAuthority = "review"
	BBoxAuthorityChildrenUnion BBoxAuthority = "children_union"
	BBoxAuthorityDerived       BBoxAuthority = "derived"
)

type Document struct {
	Version  string     `json:"version"`
	Image    ImageMeta  `json:"image"`
	Layers   []Layer    `json:"layers"`
	Groups   []Group    `json:"groups,omitempty"`
	Assets   []Asset    `json:"assets,omitempty"`
	Evidence []Evidence `json:"evidence,omitempty"`
	Summary  Summary    `json:"summary"`
}

type ImageMeta struct {
	Path            string `json:"path,omitempty"`
	Width           int    `json:"width"`
	Height          int    `json:"height"`
	SHA256          string `json:"sha256,omitempty"`
	BackgroundColor string `json:"backgroundColor,omitempty"`
}

type Layer struct {
	ID           string         `json:"id"`
	Kind         LayerKind      `json:"kind"`
	BBox         geometry.Rect  `json:"bbox"`
	Z            int            `json:"z"`
	Visible      bool           `json:"visible"`
	Locked       bool           `json:"locked,omitempty"`
	GroupID      string         `json:"groupId,omitempty"`
	Name         string         `json:"name,omitempty"`
	SemanticTags []string       `json:"semanticTags,omitempty"`
	Text         *Text          `json:"text,omitempty"`
	Raster       *Raster        `json:"raster,omitempty"`
	Shape        *Shape         `json:"shape,omitempty"`
	SourceRefs   []SourceRef    `json:"sourceRefs,omitempty"`
	Decision     Decision       `json:"decision"`
	Meta         map[string]any `json:"meta,omitempty"`
}

type Text struct {
	Characters string  `json:"characters"`
	FontSize   int     `json:"fontSize,omitempty"`
	Color      string  `json:"color,omitempty"`
	FontWeight int     `json:"fontWeight,omitempty"`
	LineHeight float64 `json:"lineHeight,omitempty"`
}

type Raster struct {
	AssetID string `json:"assetId"`
	Mode    string `json:"mode,omitempty"`
}

type Shape struct {
	Fill         string  `json:"fill,omitempty"`
	Stroke       string  `json:"stroke,omitempty"`
	CornerRadius float64 `json:"cornerRadius,omitempty"`
	Opacity      float64 `json:"opacity,omitempty"`
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

type Group struct {
	ID            string        `json:"id"`
	Kind          string        `json:"kind"`
	BBox          geometry.Rect `json:"bbox"`
	SemanticTags  []string      `json:"semanticTags,omitempty"`
	ChildLayerIDs []string      `json:"childLayerIds"`
	Decision      Decision      `json:"decision"`
}

type SourceRef struct {
	Kind string `json:"kind"`
	ID   string `json:"id"`
}

type Evidence struct {
	ID            string         `json:"id"`
	State         DecisionState  `json:"state"`
	Kind          string         `json:"kind"`
	BBox          geometry.Rect  `json:"bbox,omitempty"`
	BBoxAuthority BBoxAuthority  `json:"bboxAuthority,omitempty"`
	SourceRefs    []SourceRef    `json:"sourceRefs,omitempty"`
	Reason        string         `json:"reason"`
	Score         float64        `json:"score,omitempty"`
	LayerID       string         `json:"layerId,omitempty"`
	Meta          map[string]any `json:"meta,omitempty"`
}

type Decision struct {
	State         DecisionState `json:"state"`
	BBoxAuthority BBoxAuthority `json:"bboxAuthority"`
	Reason        string        `json:"reason"`
	SourceIDs     []string      `json:"sourceIds,omitempty"`
}

type Summary struct {
	LayerCount int            `json:"layerCount"`
	GroupCount int            `json:"groupCount"`
	AssetCount int            `json:"assetCount"`
	KindCounts map[string]int `json:"kindCounts,omitempty"`
}
