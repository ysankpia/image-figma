package relation

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/evidence"
)

type Options struct {
	InputPath string
	OutputDir string
}

func Compile(options Options) (Document, error) {
	if options.InputPath == "" {
		return Document{}, fmt.Errorf("missing input path")
	}
	if options.OutputDir == "" {
		return Document{}, fmt.Errorf("missing output dir")
	}
	source, err := readEvidenceTokens(options.InputPath)
	if err != nil {
		return Document{}, err
	}
	relations := buildRelations(source.Tokens, source.Source.ImageWidth, source.Source.ImageHeight)
	doc := Document{
		SchemaName: "M29RelationGraph",
		Version:    "1.1",
		Source: Source{
			SchemaName:  source.SchemaName,
			Version:     source.Version,
			ImageWidth:  source.Source.ImageWidth,
			ImageHeight: source.Source.ImageHeight,
			SourcePath:  source.Source.SourcePath,
			TokenCount:  len(source.Tokens),
		},
		Relations:   relations,
		Diagnostics: buildDiagnostics(source.Tokens, relations),
	}
	if err := os.MkdirAll(options.OutputDir, 0o755); err != nil {
		return Document{}, err
	}
	data, err := json.MarshalIndent(doc, "", "  ")
	if err != nil {
		return Document{}, err
	}
	if err := os.WriteFile(filepath.Join(options.OutputDir, "relation_graph.v1.json"), data, 0o644); err != nil {
		return Document{}, err
	}
	if err := writeRelationArtifacts(options.OutputDir, source.Source.SourcePath, source.Tokens, relations, doc.Diagnostics); err != nil {
		return Document{}, err
	}
	return doc, nil
}

func readEvidenceTokens(path string) (evidence.Document, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return evidence.Document{}, err
	}
	var doc evidence.Document
	if err := json.Unmarshal(data, &doc); err != nil {
		return evidence.Document{}, err
	}
	if doc.SchemaName != "M29EvidenceTokens" {
		return evidence.Document{}, fmt.Errorf("expected M29EvidenceTokens, got %q", doc.SchemaName)
	}
	return doc, nil
}

func buildRelations(tokens []evidence.Token, imageWidth int, imageHeight int) []Relation {
	eligible := eligibleTokens(tokens)
	localScale := computeLocalScale(eligible, imageWidth, imageHeight)
	var relations []Relation
	nextID := 1
	for i := range eligible {
		for j := range eligible {
			if i == j {
				continue
			}
			a := eligible[i]
			b := eligible[j]
			for _, candidate := range relationsForPair(a, b, localScale) {
				candidate.ID = fmt.Sprintf("rel_%04d", nextID)
				nextID++
				relations = append(relations, candidate)
			}
		}
	}
	sort.SliceStable(relations, func(i, j int) bool {
		if relations[i].RelationType != relations[j].RelationType {
			return relations[i].RelationType < relations[j].RelationType
		}
		if relations[i].FromID != relations[j].FromID {
			return relations[i].FromID < relations[j].FromID
		}
		return relations[i].ToID < relations[j].ToID
	})
	for i := range relations {
		relations[i].ID = fmt.Sprintf("rel_%04d", i+1)
	}
	return relations
}

func eligibleTokens(tokens []evidence.Token) []evidence.Token {
	out := make([]evidence.Token, 0, len(tokens))
	for _, token := range tokens {
		if token.Disposition == "suppressed" {
			continue
		}
		if token.BBox.Width <= 0 || token.BBox.Height <= 0 {
			continue
		}
		out = append(out, token)
	}
	return out
}

func computeLocalScale(tokens []evidence.Token, imageWidth int, imageHeight int) int {
	var heights []int
	for _, token := range tokens {
		if token.TokenType == "text_token" && token.BBox.Height > 0 {
			heights = append(heights, token.BBox.Height)
		}
	}
	if len(heights) == 0 {
		for _, token := range tokens {
			if token.BBox.Height > 0 {
				heights = append(heights, token.BBox.Height)
			}
		}
	}
	if len(heights) == 0 {
		return max(4, min(imageWidth, imageHeight)/200)
	}
	sort.Ints(heights)
	return max(4, heights[len(heights)/2])
}

func relationsForPair(a evidence.Token, b evidence.Token, localScale int) []Relation {
	var out []Relation
	m := relationMetrics(a.BBox, b.BBox)
	weak := a.Disposition == "review" || b.Disposition == "review"
	if canContainForeground(a) && contains(a.BBox, b.BBox, max(2, localScale/4)) && area(a.BBox) > area(b.BBox) {
		out = append(out, newRelation("contains", a, b, confidence(0.9, weak), weak, m, []string{"bbox_contains"}))
		if a.TokenType == "surface_region_token" {
			out = append(out, newRelation("inside_surface", b, a, confidence(0.88, weak), weak, m, []string{"foreground_inside_surface"}))
		}
		if isBackgroundToken(a) {
			out = append(out, newRelation("foreground_inside_background", b, a, confidence(0.76, weak), weak, m, []string{"foreground_inside_background"}))
		}
	}
	if m.IoU >= 0.86 {
		if canonicalPair(a, b) {
			out = append(out, newRelation("near_duplicate", a, b, confidence(0.82, weak), weak, m, []string{"high_iou"}))
		}
	}
	if m.IoU > 0 && m.IoU < 0.86 && m.IntersectionRatio >= 0.16 {
		if canonicalPair(a, b) {
			out = append(out, newRelation("overlaps", a, b, confidence(0.62, weak), weak, m, []string{"partial_bbox_overlap"}))
		}
	}
	if adjacentRelation, ok := adjacentRelationFor(a, b, localScale, m); ok && canonicalPair(a, b) {
		out = append(out, newRelation(adjacentRelation, a, b, confidence(0.72, weak), weak, m, []string{"near_edges", adjacentRelation}))
	}
	if sameRow(a, b, localScale, m) && canonicalPair(a, b) {
		out = append(out, newRelation("same_row", a, b, confidence(0.68, weak), weak, m, []string{"aligned_horizontal_band"}))
	}
	if sameColumn(a, b, localScale, m) && canonicalPair(a, b) {
		out = append(out, newRelation("same_column", a, b, confidence(0.68, weak), weak, m, []string{"aligned_vertical_band"}))
	}
	if sameBand(a, b, localScale, m) && canonicalPair(a, b) {
		out = append(out, newRelation("same_band", a, b, confidence(0.74, weak), weak, m, []string{"shared_visual_band"}))
		if a.TokenType == "raster_region_token" && b.TokenType == "raster_region_token" {
			out = append(out, newRelation("raster_parts_same_region", a, b, confidence(0.78, weak), weak, m, []string{"adjacent_raster_same_band"}))
		}
	}
	return out
}

func canonicalPair(a evidence.Token, b evidence.Token) bool {
	return a.ID < b.ID
}

func newRelation(relationType string, from evidence.Token, to evidence.Token, relationConfidence float64, weak bool, metrics Metrics, reasons []string) Relation {
	strength := "strong"
	if weak {
		strength = "weak"
	}
	return Relation{
		RelationType: relationType,
		Category:     relationCategory(relationType),
		FromID:       from.ID,
		ToID:         to.ID,
		Confidence:   relationConfidence,
		Strength:     strength,
		Metrics:      metrics,
		Reasons:      reasons,
	}
}

func relationCategory(relationType string) string {
	switch relationType {
	case "contains", "inside_surface", "foreground_inside_background":
		return "structural"
	case "raster_parts_same_region", "same_band", "near_duplicate":
		return "grouping"
	default:
		return "layout_hint"
	}
}

func canContainForeground(token evidence.Token) bool {
	switch token.TokenType {
	case "surface_region_token", "layer_background_token":
		return true
	case "raster_region_token":
		return token.CompileHints.CanContainForeground
	default:
		return false
	}
}

func isBackgroundToken(token evidence.Token) bool {
	return token.TokenType == "raster_region_token" || token.TokenType == "layer_background_token"
}

func adjacentRelationFor(a evidence.Token, b evidence.Token, localScale int, m Metrics) (string, bool) {
	maxGap := max(2, localScale)
	if m.GapX <= maxGap && m.VerticalOverlapRatio >= 0.45 {
		if a.BBox.X+a.BBox.Width <= b.BBox.X {
			return "adjacent_right", true
		}
		if b.BBox.X+b.BBox.Width <= a.BBox.X {
			return "adjacent_left", true
		}
	}
	if m.GapY <= maxGap && m.HorizontalOverlapRatio >= 0.45 {
		if a.BBox.Y+a.BBox.Height <= b.BBox.Y {
			return "adjacent_bottom", true
		}
		if b.BBox.Y+b.BBox.Height <= a.BBox.Y {
			return "adjacent_top", true
		}
	}
	return "", false
}

func sameRow(a evidence.Token, b evidence.Token, localScale int, m Metrics) bool {
	if a.ID == b.ID {
		return false
	}
	if !sameAxisCandidate(a, b, localScale, m) {
		return false
	}
	if m.VerticalOverlapRatio < 0.68 {
		return false
	}
	return m.GapX <= max(localScale*3, 8)
}

func sameColumn(a evidence.Token, b evidence.Token, localScale int, m Metrics) bool {
	if a.ID == b.ID {
		return false
	}
	if !sameAxisCandidate(a, b, localScale, m) {
		return false
	}
	if m.HorizontalOverlapRatio < 0.68 {
		return false
	}
	return m.GapY <= max(localScale*3, 8)
}

func sameAxisCandidate(a evidence.Token, b evidence.Token, localScale int, m Metrics) bool {
	if contains(a.BBox, b.BBox, max(2, localScale/4)) || contains(b.BBox, a.BBox, max(2, localScale/4)) {
		return false
	}
	if axisBackgroundCandidate(a) || axisBackgroundCandidate(b) {
		if m.AreaRatio < 0.12 {
			return false
		}
		if m.CenterDistance > float64(max(localScale*8, 96)) {
			return false
		}
	}
	return true
}

func axisBackgroundCandidate(token evidence.Token) bool {
	switch token.TokenType {
	case "raster_region_token", "surface_region_token", "layer_background_token":
		return true
	default:
		return false
	}
}

func sameBand(a evidence.Token, b evidence.Token, localScale int, m Metrics) bool {
	if a.ID == b.ID {
		return false
	}
	if contains(a.BBox, b.BBox, max(2, localScale/4)) || contains(b.BBox, a.BBox, max(2, localScale/4)) {
		return false
	}
	if m.VerticalOverlapRatio < 0.62 {
		return false
	}
	if m.GapX > max(localScale*3, 12) {
		return false
	}
	heightRatio := areaRatio(bbox{Width: 1, Height: a.BBox.Height}, bbox{Width: 1, Height: b.BBox.Height})
	if heightRatio < 0.42 {
		return false
	}
	return isBandToken(a) && isBandToken(b)
}

func isBandToken(token evidence.Token) bool {
	switch token.TokenType {
	case "raster_region_token", "surface_region_token", "layer_background_token":
		return true
	default:
		return false
	}
}

func confidence(value float64, weak bool) float64 {
	if weak {
		return round4(value * 0.72)
	}
	return round4(value)
}

func buildDiagnostics(tokens []evidence.Token, relations []Relation) Diagnostics {
	counts := map[string]int{}
	categoryCounts := map[string]int{}
	weak := 0
	eligible := 0
	for _, token := range tokens {
		if token.Disposition != "suppressed" {
			eligible++
		}
	}
	d := Diagnostics{
		TokenCount:             len(tokens),
		EligibleTokenCount:     eligible,
		RelationCount:          len(relations),
		RelationTypeCounts:     counts,
		RelationCategoryCounts: categoryCounts,
	}
	for _, relation := range relations {
		counts[relation.RelationType]++
		categoryCounts[relation.Category]++
		if relation.Strength == "weak" {
			weak++
		}
		switch relation.Category {
		case "structural":
			d.StructuralRelationCount++
		case "grouping":
			d.GroupingRelationCount++
		case "layout_hint":
			d.LayoutHintRelationCount++
		}
		switch relation.RelationType {
		case "contains":
			d.ContainsCount++
		case "inside_surface":
			d.InsideSurfaceCount++
		case "foreground_inside_background":
			d.ForegroundInsideBackgroundCount++
		case "adjacent_left", "adjacent_right", "adjacent_top", "adjacent_bottom":
			d.AdjacentCount++
		case "same_band":
			d.SameBandCount++
		case "raster_parts_same_region":
			d.RasterPartsSameRegionCount++
		case "near_duplicate":
			d.NearDuplicateCount++
		}
	}
	d.WeakRelationCount = weak
	return d
}
