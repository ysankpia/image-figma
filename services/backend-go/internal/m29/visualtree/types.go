package visualtree

import "github.com/luqing-studio/image-figma/services/backend-go/internal/m29/contract"

type Document struct {
	SchemaName        string            `json:"schemaName"`
	Version           string            `json:"version"`
	Source            Source            `json:"source"`
	Root              Node              `json:"root"`
	VisualElement     VisualElement     `json:"visualElement"`
	Diagnostics       Diagnostics       `json:"diagnostics"`
	ContainmentReport ContainmentReport `json:"containmentReport"`
}

type Source struct {
	TokenSchemaName    string `json:"tokenSchemaName"`
	TokenVersion       string `json:"tokenVersion"`
	RelationSchemaName string `json:"relationSchemaName"`
	RelationVersion    string `json:"relationVersion"`
	ImageWidth         int    `json:"imageWidth"`
	ImageHeight        int    `json:"imageHeight"`
	SourcePath         string `json:"sourcePath,omitempty"`
	TokenCount         int    `json:"tokenCount"`
	RelationCount      int    `json:"relationCount"`
}

type Node struct {
	ID         string        `json:"id"`
	Type       string        `json:"type"`
	Name       string        `json:"name"`
	BBox       contract.BBox `json:"bbox"`
	Layout     Layout        `json:"layout"`
	Style      Style         `json:"style,omitempty"`
	Content    Content       `json:"content,omitempty"`
	SourceRefs SourceRefs    `json:"sourceRefs"`
	Meta       Meta          `json:"meta,omitempty"`
	Children   []Node        `json:"children,omitempty"`
}

type Layout struct {
	Mode     string `json:"mode"`
	X        int    `json:"x"`
	Y        int    `json:"y"`
	Width    int    `json:"width"`
	Height   int    `json:"height"`
	Relative bool   `json:"relative"`
}

type Style struct {
	BackgroundRef string `json:"backgroundRef,omitempty"`
}

type Content struct {
	Text string `json:"text,omitempty"`
}

type SourceRefs struct {
	TokenIDs      []string `json:"tokenIds,omitempty"`
	RelationIDs   []string `json:"relationIds,omitempty"`
	BackgroundIDs []string `json:"backgroundTokenIds,omitempty"`
}

type Meta struct {
	Synthetic    bool   `json:"synthetic,omitempty"`
	GroupKind    string `json:"groupKind,omitempty"`
	ParentReason string `json:"parentReason,omitempty"`
}

type Diagnostics struct {
	TokenCount                  int            `json:"tokenCount"`
	RelationCount               int            `json:"relationCount"`
	NodeCount                   int            `json:"nodeCount"`
	BodyChildCount              int            `json:"bodyChildCount"`
	NodeTypeCounts              map[string]int `json:"nodeTypeCounts"`
	ParentRelationCount         int            `json:"parentRelationCount"`
	SyntheticGroupCount         int            `json:"syntheticGroupCount"`
	GroupKindCounts             map[string]int `json:"groupKindCounts,omitempty"`
	BackgroundLayerCount        int            `json:"backgroundLayerCount"`
	ParentRelativeLayoutCount   int            `json:"parentRelativeLayoutCount"`
	SuppressedTokenSkippedCount int            `json:"suppressedTokenSkippedCount"`
	ContainmentCandidateCount   int            `json:"containmentCandidateCount"`
	ContainmentAppliedCount     int            `json:"containmentAppliedCount"`
	ContainmentOnlyParentCount  int            `json:"containmentOnlyParentCount"`
	RelationParentCount         int            `json:"relationParentCount"`
	BodyChildCountBefore        int            `json:"bodyChildCountBefore"`
	BodyChildCountAfter         int            `json:"bodyChildCountAfter"`
}

type ContainmentReport struct {
	BodyChildCountBefore       int                   `json:"bodyChildCountBefore"`
	BodyChildCountAfter        int                   `json:"bodyChildCountAfter"`
	CandidateCount             int                   `json:"candidateCount"`
	AppliedCount               int                   `json:"appliedCount"`
	ContainmentOnlyParentCount int                   `json:"containmentOnlyParentCount"`
	RelationParentCount        int                   `json:"relationParentCount"`
	Decisions                  []ContainmentDecision `json:"decisions"`
}

type ContainmentDecision struct {
	NodeID        string   `json:"nodeId"`
	OldParentID   string   `json:"oldParentId"`
	NewParentID   string   `json:"newParentId"`
	NewParentKind string   `json:"newParentKind"`
	Reason        string   `json:"reason"`
	BBoxCoverage  float64  `json:"bboxCoverage"`
	RelationIDs   []string `json:"relationIds,omitempty"`
	Decision      string   `json:"decision"`
}

type VisualElementDocument struct {
	SchemaName    string        `json:"schemaName"`
	Version       string        `json:"version"`
	Source        Source        `json:"source"`
	VisualElement VisualElement `json:"visualElement"`
	Diagnostics   Diagnostics   `json:"diagnostics"`
}

type VisualElement struct {
	ElementID      string              `json:"elementId"`
	ElementName    string              `json:"elementName"`
	ElementType    string              `json:"elementType"`
	DisplayName    string              `json:"displayName,omitempty"`
	LayoutConfig   LayoutConfiguration `json:"layoutConfig"`
	StyleConfig    VisualStyle         `json:"styleConfig"`
	ProcessingMeta ProcessingMeta      `json:"processingMeta"`
	ContentData    *ElementContent     `json:"contentData,omitempty"`
	ChildElements  []VisualElement     `json:"childElements,omitempty"`
	BoundingBox    []int               `json:"boundingBox"`
}

type LayoutConfiguration struct {
	PositionMode  string        `json:"positionMode"`
	AbsoluteAttrs AbsoluteAttrs `json:"absoluteAttrs"`
}

type AbsoluteAttrs struct {
	Align      []string `json:"align"`
	Coord      []int    `json:"coord"`
	OrginCoord []int    `json:"orginCoord"`
}

type VisualStyle struct {
	WidthSpec      SizeSpec        `json:"widthSpec"`
	HeightSpec     SizeSpec        `json:"heightSpec"`
	BackgroundSpec *BackgroundSpec `json:"backgroundSpec,omitempty"`
	TextConfig     *TextConfig     `json:"textConfig,omitempty"`
	OpacityLevel   int             `json:"opacityLevel"`
}

type SizeSpec struct {
	Sizing string `json:"sizing"`
	Value  int    `json:"value"`
}

type BackgroundSpec struct {
	Type               string       `json:"type"`
	BackgroundColor    *VisualColor `json:"backgroundColor,omitempty"`
	ImageSource        string       `json:"imageSource,omitempty"`
	BackgroundSize     string       `json:"backgroundSize,omitempty"`
	BackgroundPosition string       `json:"backgroundPosition,omitempty"`
	BackgroundRepeat   string       `json:"backgroundRepeat,omitempty"`
}

type VisualColor struct {
	RGBValues []int  `json:"rgbValues"`
	HexCode   string `json:"hexCode"`
}

type TextConfig struct {
	FontSize      int      `json:"fontSize"`
	FontStyle     string   `json:"fontStyle"`
	TextAlign     []string `json:"textAlign"`
	FontFamily    string   `json:"fontFamily"`
	LineHeight    float64  `json:"lineHeight"`
	LetterSpacing int      `json:"letterSpacing"`
}

type ProcessingMeta struct {
	SourceNodeID       string   `json:"sourceNodeId"`
	SourceTokenIDs     []string `json:"sourceTokenIds,omitempty"`
	SourceRelationIDs  []string `json:"sourceRelationIds,omitempty"`
	Synthetic          bool     `json:"synthetic,omitempty"`
	GroupKind          string   `json:"groupKind,omitempty"`
	ParentReason       string   `json:"parentReason,omitempty"`
	BackgroundTokenIDs []string `json:"backgroundTokenIds,omitempty"`
}

type ElementContent struct {
	TextValue   string `json:"textValue,omitempty"`
	ImageSource string `json:"imageSource,omitempty"`
}
