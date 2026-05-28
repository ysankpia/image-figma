package relation

import (
	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/contract"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/evidence"
)

type Document struct {
	SchemaName  string      `json:"schemaName"`
	Version     string      `json:"version"`
	Source      Source      `json:"source"`
	Relations   []Relation  `json:"relations"`
	Diagnostics Diagnostics `json:"diagnostics"`
}

type Source struct {
	SchemaName  string `json:"schemaName"`
	Version     string `json:"version"`
	ImageWidth  int    `json:"imageWidth"`
	ImageHeight int    `json:"imageHeight"`
	SourcePath  string `json:"sourcePath,omitempty"`
	TokenCount  int    `json:"tokenCount"`
}

type Relation struct {
	ID           string   `json:"id"`
	RelationType string   `json:"relationType"`
	Category     string   `json:"category"`
	FromID       string   `json:"fromId"`
	ToID         string   `json:"toId"`
	Confidence   float64  `json:"confidence"`
	Strength     string   `json:"strength"`
	Metrics      Metrics  `json:"metrics"`
	Reasons      []string `json:"reasons"`
}

type Metrics struct {
	IntersectionRatio      float64 `json:"intersectionRatio,omitempty"`
	IoU                    float64 `json:"iou,omitempty"`
	ChildCoverage          float64 `json:"childCoverage,omitempty"`
	ParentCoverage         float64 `json:"parentCoverage,omitempty"`
	HorizontalOverlapRatio float64 `json:"horizontalOverlapRatio,omitempty"`
	VerticalOverlapRatio   float64 `json:"verticalOverlapRatio,omitempty"`
	GapX                   int     `json:"gapX,omitempty"`
	GapY                   int     `json:"gapY,omitempty"`
	CenterDistance         float64 `json:"centerDistance,omitempty"`
	AreaRatio              float64 `json:"areaRatio,omitempty"`
}

type Diagnostics struct {
	TokenCount                      int            `json:"tokenCount"`
	EligibleTokenCount              int            `json:"eligibleTokenCount"`
	RelationCount                   int            `json:"relationCount"`
	RelationTypeCounts              map[string]int `json:"relationTypeCounts"`
	RelationCategoryCounts          map[string]int `json:"relationCategoryCounts"`
	WeakRelationCount               int            `json:"weakRelationCount"`
	StructuralRelationCount         int            `json:"structuralRelationCount"`
	GroupingRelationCount           int            `json:"groupingRelationCount"`
	LayoutHintRelationCount         int            `json:"layoutHintRelationCount"`
	ContainsCount                   int            `json:"containsCount"`
	InsideSurfaceCount              int            `json:"insideSurfaceCount"`
	ForegroundInsideBackgroundCount int            `json:"foregroundInsideBackgroundCount"`
	AdjacentCount                   int            `json:"adjacentCount"`
	SameBandCount                   int            `json:"sameBandCount"`
	RasterPartsSameRegionCount      int            `json:"rasterPartsSameRegionCount"`
	NearDuplicateCount              int            `json:"nearDuplicateCount"`
}

type token = evidence.Token
type bbox = contract.BBox
