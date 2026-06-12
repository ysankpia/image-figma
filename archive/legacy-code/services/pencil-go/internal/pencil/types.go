package pencil

const PenVersion = "2.11"

type Mode string

const (
	ModeCleanEditable  Mode = "clean-editable"
	ModeVisualFidelity Mode = "visual-fidelity"
	ModeVisualOCR      Mode = "visual-ocr"
	ModeAll            Mode = "all"
)

func ExpandModes(mode Mode) []Mode {
	switch mode {
	case "", ModeAll:
		return []Mode{ModeCleanEditable, ModeVisualFidelity, ModeVisualOCR}
	case ModeCleanEditable, ModeVisualFidelity, ModeVisualOCR:
		return []Mode{mode}
	default:
		return []Mode{}
	}
}

type ModePolicy struct {
	Mode               Mode
	DirName            string
	VisibleOCRText     bool
	CropTextRegions    bool
	TextKnockout       bool
	CropDedupe         bool
	CropPolicy         string
	Description        string
	ForbiddenAssetRefs []string
}

func PolicyForMode(mode Mode) (ModePolicy, bool) {
	switch mode {
	case ModeCleanEditable:
		return ModePolicy{
			Mode:            mode,
			DirName:         "clean-editable",
			VisibleOCRText:  true,
			CropTextRegions: false,
			TextKnockout:    true,
			CropDedupe:      true,
			CropPolicy:      "component",
			Description:     "Clean handoff with text knockout crops plus visible editable OCR TextLayers.",
		}, true
	case ModeVisualFidelity:
		return ModePolicy{
			Mode:            mode,
			DirName:         "visual-fidelity",
			VisibleOCRText:  false,
			CropTextRegions: true,
			TextKnockout:    false,
			CropDedupe:      false,
			CropPolicy:      "disabled",
			Description:     "Crop-only visual handoff. OCR text stays in the bitmap; no visible OCR TextLayers.",
		}, true
	case ModeVisualOCR:
		return ModePolicy{
			Mode:            mode,
			DirName:         "visual-ocr",
			VisibleOCRText:  true,
			CropTextRegions: true,
			TextKnockout:    false,
			CropDedupe:      false,
			CropPolicy:      "disabled",
			Description:     "Visual-fidelity bitmap layers with high-contrast visible OCR TextLayers overlaid.",
		}, true
	default:
		return ModePolicy{}, false
	}
}

type Document struct {
	Version  string `json:"version"`
	Children []Node `json:"children"`
}

type Node map[string]any

type Manifest struct {
	Schema                       string           `json:"schema"`
	Pen                          string           `json:"pen"`
	Mode                         Mode             `json:"mode"`
	ModeDescription              string           `json:"modeDescription"`
	Canvas                       Canvas           `json:"canvas"`
	CropPolicy                   string           `json:"cropPolicy"`
	VisibleOCRText               bool             `json:"visibleOcrText"`
	CropTextRegions              bool             `json:"cropTextRegions"`
	Counts                       map[string]int   `json:"counts"`
	TextNodes                    int              `json:"textNodes"`
	CropNodes                    int              `json:"cropNodes"`
	TextKnockoutCropNodes        int              `json:"textKnockoutCropNodes"`
	ArtTextCropNodes             int              `json:"artTextCropNodes"`
	CropTextNodes                int              `json:"cropTextNodes"`
	SuppressedDuplicateCropNodes int              `json:"suppressedDuplicateCropNodes"`
	SuppressedInternalCropNodes  int              `json:"suppressedInternalCropNodes"`
	TextDecisions                []TextDecision   `json:"textDecisions"`
	SuppressedCropLayers         []SuppressedCrop `json:"suppressedCropLayers"`
	Assets                       []Asset          `json:"assets"`
	FontPolicy                   FontPolicy       `json:"fontPolicy"`
	ProductionGuarantees         Guarantees       `json:"productionGuarantees"`
}

type Canvas struct {
	Width  int    `json:"width"`
	Height int    `json:"height"`
	Fill   string `json:"fill"`
}

type TextDecision struct {
	PrimitiveID string `json:"primitiveId"`
	Text        string `json:"text"`
	Decision    string `json:"decision"`
	Reason      string `json:"reason"`
}

type SuppressedCrop struct {
	ID              string  `json:"id"`
	PrimitiveID     string  `json:"primitiveId,omitempty"`
	Role            string  `json:"role,omitempty"`
	Reason          string  `json:"reason"`
	DuplicateOf     string  `json:"duplicateOf,omitempty"`
	DuplicateOfRole string  `json:"duplicateOfRole,omitempty"`
	RootReason      string  `json:"rootReason,omitempty"`
	IOAToOwner      float64 `json:"ioaToOwner,omitempty"`
}

type Asset struct {
	PrimitiveID        string `json:"primitiveId"`
	Role               string `json:"role"`
	URL                string `json:"url"`
	VisibleAssetSource string `json:"visibleAssetSource"`
	SourceCropRef      string `json:"sourceCropRef"`
	TextKnockout       bool   `json:"textKnockout,omitempty"`
	KnockoutPixelCount int    `json:"knockoutPixelCount,omitempty"`
}

type FontPolicy struct {
	PenPreviewFontFamily string   `json:"penPreviewFontFamily"`
	CJKOrMixedCandidates []string `json:"cjkOrMixedCandidates"`
	LatinCandidates      []string `json:"latinCandidates"`
	FigmaImportRule      string   `json:"figmaImportRule"`
	TextGrowth           string   `json:"textGrowth"`
	LineHeight           float64  `json:"lineHeight"`
	VerticalAlign        string   `json:"verticalAlign"`
}

type Guarantees struct {
	ReferencesSourceImage     bool `json:"referencesSourceImage"`
	ReferencesRawCrops        bool `json:"referencesRawCrops"`
	ReferencesMasks           bool `json:"referencesMasks"`
	ReferencesTextRegionCrops bool `json:"referencesTextRegionCrops"`
}

type ProjectManifest struct {
	Schema      string              `json:"schema"`
	ProjectName string              `json:"projectName"`
	PageCount   int                 `json:"pageCount"`
	Modes       []Mode              `json:"modes"`
	Pages       []ProjectPage       `json:"pages"`
	ModeOutputs map[Mode]ModeOutput `json:"modeOutputs"`
}

type ProjectPage struct {
	PageID     string           `json:"pageId"`
	Name       string           `json:"name"`
	SourcePath string           `json:"sourcePath"`
	Width      int              `json:"width"`
	Height     int              `json:"height"`
	X          int              `json:"x"`
	Y          int              `json:"y"`
	Summaries  map[Mode]Summary `json:"summaries"`
}

type ModeOutput struct {
	Pen      string  `json:"pen"`
	Manifest string  `json:"manifest"`
	Summary  Summary `json:"summary"`
}

type Summary struct {
	TextNodes                    int `json:"textNodes"`
	CropNodes                    int `json:"cropNodes"`
	TextKnockoutCropNodes        int `json:"textKnockoutCropNodes"`
	ArtTextCropNodes             int `json:"artTextCropNodes"`
	CropTextNodes                int `json:"cropTextNodes"`
	SuppressedDuplicateCropNodes int `json:"suppressedDuplicateCropNodes"`
	SuppressedInternalCropNodes  int `json:"suppressedInternalCropNodes"`
	AssetCount                   int `json:"assetCount"`
}
