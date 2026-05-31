package canvas

type BBox struct {
	X      int `json:"x"`
	Y      int `json:"y"`
	Width  int `json:"width"`
	Height int `json:"height"`
}

type Analysis struct {
	SchemaName            string                     `json:"schemaName"`
	Version               string                     `json:"version"`
	InputPath             string                     `json:"inputPath"`
	CanvasVersion         int                        `json:"canvasVersion"`
	DesignFramePath       string                     `json:"designFramePath"`
	DesignFrameName       string                     `json:"designFrameName"`
	RootPath              string                     `json:"rootPath"`
	RootName              string                     `json:"rootName"`
	RootBBox              BBox                       `json:"rootBBox"`
	RootChildCount        int                        `json:"rootChildCount"`
	NodeCount             int                        `json:"nodeCount"`
	MaxDepth              int                        `json:"maxDepth"`
	TypeCounts            map[string]int             `json:"typeCounts"`
	NameCounts            map[string]int             `json:"nameCounts"`
	RoleCounts            map[string]int             `json:"roleCounts"`
	GUIDCoverage          Coverage                   `json:"guidCoverage"`
	SchemaCoverage        Coverage                   `json:"schemaCoverage"`
	Suffix                SuffixReport               `json:"suffix"`
	ChildOrder            ChildOrderReport           `json:"childOrder"`
	LastChild             map[string]LastChildReport `json:"lastChild"`
	ButtonModes           map[string]int             `json:"buttonModes"`
	EditTextModes         map[string]int             `json:"editTextModes"`
	Text                  TextReport                 `json:"text"`
	ImageFills            ImageFillReport            `json:"imageFills"`
	CornerRadius          CornerRadiusReport         `json:"cornerRadius"`
	Overflow              OverflowReport             `json:"overflow"`
	SiblingOverlap        SiblingOverlapReport       `json:"siblingOverlap"`
	RoleMappingViolations []RoleMappingViolation     `json:"roleMappingViolations,omitempty"`
	Expectation           string                     `json:"expectation,omitempty"`
	ExpectationFailures   []ExpectationFailure       `json:"expectationFailures,omitempty"`
	Nodes                 []NodeFact                 `json:"nodes"`
}

type Coverage struct {
	Present int `json:"present"`
	Total   int `json:"total"`
}

type SuffixReport struct {
	Present    int   `json:"present"`
	Min        int   `json:"min"`
	Max        int   `json:"max"`
	Missing    []int `json:"missing,omitempty"`
	Duplicates []int `json:"duplicates,omitempty"`
}

type ChildOrderReport struct {
	MultiChildParents       int                   `json:"multiChildParents"`
	StrictDescendingParents int                   `json:"strictDescendingParents"`
	Violations              []ChildOrderViolation `json:"violations,omitempty"`
}

type ChildOrderViolation struct {
	Path     string   `json:"path"`
	SchemaID string   `json:"schemaId,omitempty"`
	Children []string `json:"children"`
	Seqs     []int    `json:"seqs"`
}

type LastChildReport struct {
	Total   int      `json:"total"`
	Last    int      `json:"last"`
	NotLast []string `json:"notLast,omitempty"`
}

type TextReport struct {
	TextViewCount      int            `json:"textViewCount"`
	NameCharacterMatch int            `json:"nameCharacterMatch"`
	Mismatches         []TextMismatch `json:"mismatches,omitempty"`
	FontCounts         map[string]int `json:"fontCounts,omitempty"`
	FontSizeMin        int            `json:"fontSizeMin,omitempty"`
	FontSizeMax        int            `json:"fontSizeMax,omitempty"`
	FontSizeMedian     int            `json:"fontSizeMedian,omitempty"`
	AutoResizeCounts   map[string]int `json:"autoResizeCounts,omitempty"`
	LineHeightCounts   map[string]int `json:"lineHeightCounts,omitempty"`
	AlignVerticalCount map[string]int `json:"alignVerticalCounts,omitempty"`
}

type TextMismatch struct {
	Path       string `json:"path"`
	SchemaID   string `json:"schemaId,omitempty"`
	Name       string `json:"name"`
	Characters string `json:"characters"`
}

type ImageFillReport struct {
	ImageFillCount  int `json:"imageFillCount"`
	UniqueHashCount int `json:"uniqueHashCount"`
}

type OverflowReport struct {
	Count int            `json:"count"`
	Items []OverflowItem `json:"items,omitempty"`
}

type OverflowItem struct {
	Path           string `json:"path"`
	SchemaID       string `json:"schemaId,omitempty"`
	ParentPath     string `json:"parentPath"`
	ParentSchemaID string `json:"parentSchemaId,omitempty"`
	DeltaLeft      int    `json:"deltaLeft"`
	DeltaTop       int    `json:"deltaTop"`
	DeltaRight     int    `json:"deltaRight"`
	DeltaBottom    int    `json:"deltaBottom"`
}

type SiblingOverlapReport struct {
	PairCount int                  `json:"pairCount"`
	ByParent  map[string]int       `json:"byParent,omitempty"`
	Samples   []SiblingOverlapItem `json:"samples,omitempty"`
}

type SiblingOverlapItem struct {
	ParentPath     string `json:"parentPath"`
	ParentSchemaID string `json:"parentSchemaId,omitempty"`
	LeftPath       string `json:"leftPath"`
	LeftSchemaID   string `json:"leftSchemaId,omitempty"`
	RightPath      string `json:"rightPath"`
	RightSchemaID  string `json:"rightSchemaId,omitempty"`
	Intersection   int    `json:"intersection"`
}

type RoleMappingViolation struct {
	Path       string `json:"path"`
	SchemaID   string `json:"schemaId,omitempty"`
	Role       string `json:"role,omitempty"`
	Type       string `json:"type"`
	Name       string `json:"name"`
	Reason     string `json:"reason"`
	Characters string `json:"characters,omitempty"`
}

type ExpectationFailure struct {
	Check    string `json:"check"`
	Expected string `json:"expected"`
	Actual   string `json:"actual"`
}

type NodeFact struct {
	Path           string        `json:"path"`
	ParentPath     string        `json:"parentPath,omitempty"`
	GUID           string        `json:"guid,omitempty"`
	Type           string        `json:"type"`
	Name           string        `json:"name"`
	Role           string        `json:"role,omitempty"`
	SchemaID       string        `json:"schemaId,omitempty"`
	SchemaX        int           `json:"schemaX,omitempty"`
	SchemaY        int           `json:"schemaY,omitempty"`
	SchemaSeq      int           `json:"schemaSeq,omitempty"`
	HasSchemaSeq   bool          `json:"hasSchemaSeq,omitempty"`
	BBox           BBox          `json:"bbox"`
	Depth          int           `json:"depth"`
	ChildCount     int           `json:"childCount"`
	TextCharacters string        `json:"textCharacters,omitempty"`
	ChildRoles     []string      `json:"childRoles,omitempty"`
	ChildSchemaIDs []string      `json:"childSchemaIds,omitempty"`
	FillTypes      []string      `json:"fillTypes,omitempty"`
	ImageHashes    []string      `json:"imageHashes,omitempty"`
	CornerRadius   *CornerRadius `json:"cornerRadius,omitempty"`
	Source         *CanvasNode   `json:"-"`
	Parent         *NodeFact     `json:"-"`
	Children       []*NodeFact   `json:"-"`
	Schema         SchemaIDInfo  `json:"-"`
}

type CornerRadiusReport struct {
	NodeCount int            `json:"nodeCount"`
	ByRole    map[string]int `json:"byRole,omitempty"`
}

type CornerRadius struct {
	TopLeft     float64 `json:"topLeft"`
	TopRight    float64 `json:"topRight"`
	BottomLeft  float64 `json:"bottomLeft"`
	BottomRight float64 `json:"bottomRight"`
	Independent bool    `json:"independent"`
}

type SchemaIDInfo struct {
	Raw   string
	Role  string
	X     int
	Y     int
	Seq   int
	Valid bool
}

type CanvasDocument struct {
	Version int        `json:"version"`
	Root    CanvasNode `json:"root"`
}

type CanvasNode struct {
	GUID                  *GUID          `json:"guid,omitempty"`
	Type                  string         `json:"type,omitempty"`
	Name                  string         `json:"name,omitempty"`
	Visible               bool           `json:"visible,omitempty"`
	Transform             Transform      `json:"transform,omitempty"`
	Size                  Size           `json:"size,omitempty"`
	PluginData            []PluginDatum  `json:"pluginData,omitempty"`
	FillPaints            []Paint        `json:"fillPaints,omitempty"`
	TextData              *TextData      `json:"textData,omitempty"`
	FontName              *FontName      `json:"fontName,omitempty"`
	FontSize              float64        `json:"fontSize,omitempty"`
	LineHeight            *LineHeight    `json:"lineHeight,omitempty"`
	TextAlignVertical     string         `json:"textAlignVertical,omitempty"`
	TextAutoResize        string         `json:"textAutoResize,omitempty"`
	RectTopLeftRadius     *float64       `json:"rectangleTopLeftCornerRadius,omitempty"`
	RectTopRightRadius    *float64       `json:"rectangleTopRightCornerRadius,omitempty"`
	RectBottomLeftRadius  *float64       `json:"rectangleBottomLeftCornerRadius,omitempty"`
	RectBottomRightRadius *float64       `json:"rectangleBottomRightCornerRadius,omitempty"`
	RectRadiiIndependent  bool           `json:"rectangleCornerRadiiIndependent,omitempty"`
	Children              []CanvasNode   `json:"children,omitempty"`
	AdditionalRawFields   map[string]any `json:"-"`
}

type GUID struct {
	SessionID int `json:"sessionID"`
	LocalID   int `json:"localID"`
}

type Transform struct {
	M00 float64 `json:"m00"`
	M01 float64 `json:"m01"`
	M02 float64 `json:"m02"`
	M10 float64 `json:"m10"`
	M11 float64 `json:"m11"`
	M12 float64 `json:"m12"`
}

type Size struct {
	X float64 `json:"x"`
	Y float64 `json:"y"`
}

type PluginDatum struct {
	PluginID string `json:"pluginID"`
	Key      string `json:"key"`
	Value    string `json:"value"`
}

type Paint struct {
	Type           string    `json:"type"`
	Color          *Color    `json:"color,omitempty"`
	Image          *ImageRef `json:"image,omitempty"`
	ImageThumbnail *ImageRef `json:"imageThumbnail,omitempty"`
}

type Color struct {
	R float64 `json:"r"`
	G float64 `json:"g"`
	B float64 `json:"b"`
	A float64 `json:"a"`
}

type ImageRef struct {
	Hash []int  `json:"hash,omitempty"`
	Name string `json:"name,omitempty"`
}

type TextData struct {
	Characters string `json:"characters"`
}

type FontName struct {
	Family     string `json:"family"`
	Style      string `json:"style"`
	Postscript string `json:"postscript"`
}

type LineHeight struct {
	Value float64 `json:"value"`
	Units string  `json:"units"`
}
