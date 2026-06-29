package contract

type BBox struct {
	X      int `json:"x"`
	Y      int `json:"y"`
	Width  int `json:"width"`
	Height int `json:"height"`
}

type Document struct {
	SchemaName  string      `json:"schemaName"`
	Version     string      `json:"version"`
	Generator   Generator   `json:"generator"`
	Image       ImageInfo   `json:"image"`
	Items       []Item      `json:"items"`
	Diagnostics Diagnostics `json:"diagnostics"`
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

type Item struct {
	ID           string       `json:"id"`
	Kind         string       `json:"kind"`
	BBox         BBox         `json:"bbox"`
	CropPath     string       `json:"cropPath"`
	Measurements Measurements `json:"measurements"`
	Hints        Hints        `json:"hints"`
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
}

type Hints struct {
	CanBeLayerBackground  bool     `json:"canBeLayerBackground"`
	CanContainForeground  bool     `json:"canContainForeground"`
	CanBeImage            bool     `json:"canBeImage"`
	CanBeIcon             bool     `json:"canBeIcon"`
	HasStableRectGeometry bool     `json:"hasStableRectGeometry"`
	Confidence            float64  `json:"confidence"`
	Reasons               []string `json:"reasons"`
}

type Diagnostics struct {
	BackgroundColor      string  `json:"backgroundColor"`
	ForegroundThreshold  float64 `json:"foregroundThreshold"`
	ForegroundPixelCount int     `json:"foregroundPixelCount"`
	ComponentCount       int     `json:"componentCount"`
	ItemCount            int     `json:"itemCount"`
}
