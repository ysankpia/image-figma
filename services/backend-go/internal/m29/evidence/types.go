package evidence

import "github.com/luqing-studio/image-figma/services/backend-go/internal/m29/contract"

type Document struct {
	SchemaName  string      `json:"schemaName"`
	Version     string      `json:"version"`
	Source      Source      `json:"source"`
	Tokens      []Token     `json:"tokens"`
	Diagnostics Diagnostics `json:"diagnostics"`
}

type Source struct {
	SchemaName     string `json:"schemaName"`
	Version        string `json:"version"`
	ImageWidth     int    `json:"imageWidth"`
	ImageHeight    int    `json:"imageHeight"`
	SourcePath     string `json:"sourcePath,omitempty"`
	PrimitiveCount int    `json:"primitiveCount"`
}

type Token struct {
	ID                 string                `json:"id"`
	TokenType          string                `json:"tokenType"`
	BBox               contract.BBox         `json:"bbox"`
	SourcePrimitiveIDs []string              `json:"sourcePrimitiveIds"`
	Content            TokenContent          `json:"content,omitempty"`
	Measurements       TokenMeasurements     `json:"measurements"`
	Disposition        string                `json:"disposition"`
	Reasons            []string              `json:"reasons"`
	CompileHints       contract.CompileHints `json:"compileHints"`
}

type TokenContent struct {
	Text string `json:"text,omitempty"`
}

type TokenMeasurements struct {
	Area                  int     `json:"area"`
	PrimitiveCount        int     `json:"primitiveCount"`
	MeanColor             string  `json:"meanColor,omitempty"`
	ColorCount            int     `json:"colorCount,omitempty"`
	EdgeDensity           float64 `json:"edgeDensity,omitempty"`
	TextureScore          float64 `json:"textureScore,omitempty"`
	CornerRadiusEstimate  float64 `json:"cornerRadiusEstimate,omitempty"`
	MaxChildAreaRatio     float64 `json:"maxChildAreaRatio,omitempty"`
	ContainedByRasterID   string  `json:"containedByRasterId,omitempty"`
	OriginalPrimitiveType string  `json:"originalPrimitiveType,omitempty"`
}

type Diagnostics struct {
	TokenCount                   int            `json:"tokenCount"`
	TokenTypeCounts              map[string]int `json:"tokenTypeCounts"`
	PrimitiveCount               int            `json:"primitiveCount"`
	MainTokenCount               int            `json:"mainTokenCount"`
	ReviewTokenCount             int            `json:"reviewTokenCount"`
	SuppressedCount              int            `json:"suppressedCount"`
	ClusteredCount               int            `json:"clusteredCount"`
	TextTokenCount               int            `json:"textTokenCount"`
	RasterTokenCount             int            `json:"rasterTokenCount"`
	SurfaceTokenCount            int            `json:"surfaceTokenCount"`
	OversizedClusterReviewCount  int            `json:"oversizedClusterReviewCount"`
	LowDensityClusterReviewCount int            `json:"lowDensityClusterReviewCount"`
	HighAspectClusterReviewCount int            `json:"highAspectClusterReviewCount"`
}
