package contract

type BBox struct {
	X      int `json:"x"`
	Y      int `json:"y"`
	Width  int `json:"width"`
	Height int `json:"height"`
}

type Document struct {
	SchemaName        string             `json:"schemaName"`
	Version           string             `json:"version"`
	Generator         Generator          `json:"generator"`
	Image             ImageInfo          `json:"image"`
	OCR               OCRInfo            `json:"ocr"`
	Primitives        []Primitive        `json:"primitives"`
	PhysicalRelations []PhysicalRelation `json:"physicalRelations"`
	Assets            []Asset            `json:"assets"`
	Diagnostics       Diagnostics        `json:"diagnostics"`
}

type Generator struct {
	Name string `json:"name"`
	Mode string `json:"mode"`
}

type ImageInfo struct {
	Width      int    `json:"width"`
	Height     int    `json:"height"`
	SourcePath string `json:"sourcePath"`
}

type OCRInfo struct {
	Provided   bool `json:"provided"`
	BlockCount int  `json:"blockCount"`
}

type Primitive struct {
	ID            string       `json:"id"`
	PrimitiveType string       `json:"primitiveType"`
	BBox          BBox         `json:"bbox"`
	MaskRef       string       `json:"maskRef,omitempty"`
	CropRef       string       `json:"cropRef,omitempty"`
	Source        Source       `json:"source"`
	Measurements  Measurements `json:"measurements"`
	CompileHints  CompileHints `json:"compileHints"`
}

type Source struct {
	Kind       string `json:"kind"`
	OCRBlockID string `json:"ocrBlockId,omitempty"`
	Text       string `json:"text,omitempty"`
}

type Measurements struct {
	Area                 int     `json:"area"`
	FillRatio            float64 `json:"fillRatio"`
	MeanColor            string  `json:"meanColor"`
	ColorCount           int     `json:"colorCount"`
	EdgeDensity          float64 `json:"edgeDensity"`
	TextureScore         float64 `json:"textureScore"`
	LocalContrast        float64 `json:"localContrast"`
	CornerRadiusEstimate float64 `json:"cornerRadiusEstimate"`
	TextMaskArea         int     `json:"textMaskArea,omitempty"`
}

type CompileHints struct {
	CanBeLayerBackground  bool     `json:"canBeLayerBackground"`
	CanContainForeground  bool     `json:"canContainForeground"`
	CanBeImage            bool     `json:"canBeImage"`
	CanBeIcon             bool     `json:"canBeIcon"`
	HasStableRectGeometry bool     `json:"hasStableRectGeometry"`
	Confidence            float64  `json:"confidence"`
	Reasons               []string `json:"reasons"`
}

type PhysicalRelation struct {
	ID       string  `json:"id"`
	Kind     string  `json:"kind"`
	FromID   string  `json:"fromId"`
	ToID     string  `json:"toId"`
	Distance float64 `json:"distance,omitempty"`
	Ratio    float64 `json:"ratio,omitempty"`
}

type Asset struct {
	ID          string `json:"id"`
	PrimitiveID string `json:"primitiveId"`
	Kind        string `json:"kind"`
	Path        string `json:"path"`
}

type Diagnostics struct {
	BackgroundColor      string  `json:"backgroundColor"`
	ForegroundThreshold  float64 `json:"foregroundThreshold"`
	ForegroundPixelCount int     `json:"foregroundPixelCount"`
	ComponentCount       int     `json:"componentCount"`
	PrimitiveCount       int     `json:"primitiveCount"`
	TextMaskPixelCount   int     `json:"textMaskPixelCount"`
}
