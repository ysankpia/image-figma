package ir

type Role string

const (
	RoleRoot             Role = "root"
	RoleViewGroup        Role = "ViewGroup"
	RoleListView         Role = "ListView"
	RoleActionBar        Role = "ActionBar"
	RoleStatusBar        Role = "StatusBar"
	RoleBottomNavigation Role = "BottomNavigation"
	RoleButton           Role = "Button"
	RoleEditText         Role = "EditText"
	RoleTextView         Role = "TextView"
	RoleImageView        Role = "ImageView"
	RoleBackground       Role = "Background"
	RoleBgButton         Role = "bg_Button"
	RoleBgEditText       Role = "bg_EditText"
)

type FigmaType string

const (
	FigmaFrame            FigmaType = "FRAME"
	FigmaText             FigmaType = "TEXT"
	FigmaRoundedRectangle FigmaType = "ROUNDED_RECTANGLE"
)

type BBox struct {
	X      int `json:"x"`
	Y      int `json:"y"`
	Width  int `json:"width"`
	Height int `json:"height"`
}

type Document struct {
	SchemaName string  `json:"schemaName"`
	Version    string  `json:"version"`
	Source     Source  `json:"source"`
	Root       Node    `json:"root"`
	Summary    Summary `json:"summary"`
}

type Source struct {
	InputPath       string `json:"inputPath,omitempty"`
	CanvasVersion   int    `json:"canvasVersion,omitempty"`
	DesignFramePath string `json:"designFramePath,omitempty"`
	DesignFrameName string `json:"designFrameName,omitempty"`
	RootPath        string `json:"rootPath,omitempty"`
}

type Summary struct {
	NodeCount       int            `json:"nodeCount"`
	MaxDepth        int            `json:"maxDepth"`
	RoleCounts      map[string]int `json:"roleCounts"`
	FigmaTypeCounts map[string]int `json:"figmaTypeCounts"`
}

type Node struct {
	ID          string     `json:"id"`
	Role        Role       `json:"role"`
	SourceBBox  BBox       `json:"source_bbox"`
	FigmaBBox   BBox       `json:"figma_bbox"`
	FigmaType   FigmaType  `json:"figma_type"`
	VisibleName string     `json:"visible_name"`
	SchemaID    string     `json:"schema_id"`
	Seq         int        `json:"seq"`
	HasSeq      bool       `json:"has_seq"`
	SourceGUID  string     `json:"source_guid,omitempty"`
	SourcePath  string     `json:"source_path,omitempty"`
	Evidence    []Evidence `json:"evidence,omitempty"`
	Style       Style      `json:"style,omitempty"`
	Text        *Text      `json:"text,omitempty"`
	Asset       *Asset     `json:"asset,omitempty"`
	Children    []Node     `json:"children,omitempty"`
}

type Evidence struct {
	Kind       string  `json:"kind"`
	BBox       BBox    `json:"bbox"`
	Confidence float64 `json:"confidence"`
	SourceID   string  `json:"source_id,omitempty"`
	Notes      string  `json:"notes,omitempty"`
}

type Style struct {
	Opacity       float64       `json:"opacity,omitempty"`
	Visible       bool          `json:"visible"`
	FillPaints    []Paint       `json:"fillPaints,omitempty"`
	CornerRadius  *CornerRadius `json:"cornerRadius,omitempty"`
	Font          *Font         `json:"font,omitempty"`
	LineHeight    *LineHeight   `json:"lineHeight,omitempty"`
	TextAlignVert string        `json:"textAlignVertical,omitempty"`
}

type Paint struct {
	Type  string `json:"type"`
	Color *Color `json:"color,omitempty"`
	Hash  string `json:"hash,omitempty"`
}

type Color struct {
	R float64 `json:"r"`
	G float64 `json:"g"`
	B float64 `json:"b"`
	A float64 `json:"a"`
}

type CornerRadius struct {
	TopLeft     float64 `json:"topLeft"`
	TopRight    float64 `json:"topRight"`
	BottomLeft  float64 `json:"bottomLeft"`
	BottomRight float64 `json:"bottomRight"`
	Independent bool    `json:"independent"`
}

type Font struct {
	Family     string  `json:"family"`
	Style      string  `json:"style,omitempty"`
	Postscript string  `json:"postscript,omitempty"`
	Size       float64 `json:"size,omitempty"`
}

type LineHeight struct {
	Value float64 `json:"value"`
	Units string  `json:"units"`
}

type Text struct {
	Characters string `json:"characters"`
}

type Asset struct {
	Kind string `json:"kind"`
	Hash string `json:"hash,omitempty"`
}
