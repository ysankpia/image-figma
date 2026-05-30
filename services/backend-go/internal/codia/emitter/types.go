package emitter

import "github.com/luqing-studio/image-figma/services/backend-go/internal/codia/ir"

type Document struct {
	SchemaName string  `json:"schemaName"`
	Version    string  `json:"version"`
	Source     Source  `json:"source"`
	Root       Node    `json:"root"`
	Summary    Summary `json:"summary"`
}

type Source struct {
	IRSchemaName string `json:"irSchemaName"`
	IRVersion    string `json:"irVersion"`
	InputPath    string `json:"inputPath,omitempty"`
	RootPath     string `json:"rootPath,omitempty"`
}

type Summary struct {
	NodeCount       int            `json:"nodeCount"`
	MaxDepth        int            `json:"maxDepth"`
	RoleCounts      map[string]int `json:"roleCounts"`
	FigmaTypeCounts map[string]int `json:"figmaTypeCounts"`
}

type Node struct {
	ID           string       `json:"id"`
	Type         ir.FigmaType `json:"type"`
	Name         string       `json:"name"`
	Role         ir.Role      `json:"role"`
	SchemaID     string       `json:"schema_id"`
	Seq          int          `json:"seq"`
	SourceBBox   ir.BBox      `json:"source_bbox"`
	FigmaBBox    ir.BBox      `json:"figma_bbox"`
	RelativeBBox ir.BBox      `json:"relative_bbox"`
	Text         *ir.Text     `json:"text,omitempty"`
	Asset        *ir.Asset    `json:"asset,omitempty"`
	Style        ir.Style     `json:"style,omitempty"`
	Children     []Node       `json:"children,omitempty"`
}
