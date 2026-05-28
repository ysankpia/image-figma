package evidence

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/contract"
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
	source, err := readPhysicalEvidence(options.InputPath)
	if err != nil {
		return Document{}, err
	}
	tokens := compileTokens(source)
	doc := Document{
		SchemaName: "M29EvidenceTokens",
		Version:    "1.0",
		Source: Source{
			SchemaName:     source.SchemaName,
			Version:        source.Version,
			ImageWidth:     source.Image.Width,
			ImageHeight:    source.Image.Height,
			SourcePath:     source.Image.SourcePath,
			PrimitiveCount: len(source.Primitives),
		},
		Tokens:      tokens,
		Diagnostics: buildDiagnostics(source, tokens),
	}
	if err := os.MkdirAll(options.OutputDir, 0o755); err != nil {
		return Document{}, err
	}
	data, err := json.MarshalIndent(doc, "", "  ")
	if err != nil {
		return Document{}, err
	}
	if err := os.WriteFile(filepath.Join(options.OutputDir, "evidence_tokens.v1.json"), data, 0o644); err != nil {
		return Document{}, err
	}
	if err := writeTokenArtifacts(options.OutputDir, source.Image.SourcePath, tokens); err != nil {
		return Document{}, err
	}
	return doc, nil
}

func readPhysicalEvidence(path string) (contract.Document, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return contract.Document{}, err
	}
	var doc contract.Document
	if err := json.Unmarshal(data, &doc); err != nil {
		return contract.Document{}, err
	}
	if doc.SchemaName != "M29PhysicalEvidence" {
		return contract.Document{}, fmt.Errorf("expected M29PhysicalEvidence, got %q", doc.SchemaName)
	}
	return doc, nil
}

func compileTokens(source contract.Document) []Token {
	primitives := append([]contract.Primitive(nil), source.Primitives...)
	sort.SliceStable(primitives, func(i, j int) bool {
		a, b := primitives[i].BBox, primitives[j].BBox
		if a.Y != b.Y {
			return a.Y < b.Y
		}
		if a.X != b.X {
			return a.X < b.X
		}
		return primitives[i].ID < primitives[j].ID
	})

	rasterParents := rasterParentPrimitives(primitives, source.Image.Width*source.Image.Height)
	consumed := map[string]bool{}
	var tokens []Token
	nextID := 1

	for _, primitive := range primitives {
		if primitive.PrimitiveType == "text_region" {
			tokens = append(tokens, tokenFromPrimitive(nextID, "text_token", primitive, "main", []string{"ocr_text_region"}))
			nextID++
			consumed[primitive.ID] = true
		}
	}

	surfaceParents := surfaceParentPrimitives(primitives)
	for _, primitive := range primitives {
		if consumed[primitive.ID] {
			continue
		}
		if primitive.PrimitiveType == "surface_region" {
			tokens = append(tokens, tokenFromPrimitive(nextID, "surface_region_token", primitive, "main", []string{"surface_region"}))
			nextID++
			consumed[primitive.ID] = true
		}
	}

	for _, primitive := range primitives {
		if consumed[primitive.ID] {
			continue
		}
		if isRasterParent(primitive, rasterParents) {
			tokens = append(tokens, tokenFromPrimitive(nextID, "raster_region_token", primitive, "main", []string{"raster_region"}))
			nextID++
			consumed[primitive.ID] = true
		}
	}

	for _, primitive := range primitives {
		if consumed[primitive.ID] {
			continue
		}
		if containingSurfaceParentID(primitive, surfaceParents) != "" {
			continue
		}
		if parentID := containingRasterParentID(primitive, rasterParents); parentID != "" {
			token := tokenFromPrimitive(nextID, "texture_fragment_token", primitive, "suppressed", []string{"inside_raster_region", "texture_fragment_not_ast_candidate"})
			token.Measurements.ContainedByRasterID = parentID
			tokens = append(tokens, token)
			nextID++
			consumed[primitive.ID] = true
		}
	}

	clusters := clusterSymbols(primitives, consumed)
	for _, cluster := range clusters {
		token := tokenFromCluster(nextID, cluster)
		tokens = append(tokens, token)
		nextID++
		for _, item := range cluster {
			consumed[item.ID] = true
		}
	}

	for _, primitive := range primitives {
		if consumed[primitive.ID] {
			continue
		}
		tokenType := tokenTypeForPrimitive(primitive)
		disposition := "main"
		reasons := []string{primitive.PrimitiveType}
		if tokenType == "unknown_token" {
			disposition = "review"
		}
		tokens = append(tokens, tokenFromPrimitive(nextID, tokenType, primitive, disposition, reasons))
		nextID++
		consumed[primitive.ID] = true
	}
	sort.SliceStable(tokens, func(i, j int) bool {
		a, b := tokens[i].BBox, tokens[j].BBox
		if a.Y != b.Y {
			return a.Y < b.Y
		}
		if a.X != b.X {
			return a.X < b.X
		}
		return tokens[i].ID < tokens[j].ID
	})
	return tokens
}

func surfaceParentPrimitives(primitives []contract.Primitive) []contract.Primitive {
	var out []contract.Primitive
	for _, p := range primitives {
		if p.PrimitiveType == "surface_region" {
			out = append(out, p)
		}
	}
	sort.SliceStable(out, func(i, j int) bool {
		return area(out[i].BBox) > area(out[j].BBox)
	})
	return out
}

func rasterParentPrimitives(primitives []contract.Primitive, imageArea int) []contract.Primitive {
	var out []contract.Primitive
	for _, p := range primitives {
		if p.PrimitiveType != "image_region" {
			continue
		}
		if area(p.BBox) < max(1, imageArea/2000) {
			continue
		}
		out = append(out, p)
	}
	sort.SliceStable(out, func(i, j int) bool {
		return area(out[i].BBox) > area(out[j].BBox)
	})
	return out
}

func isRasterParent(p contract.Primitive, parents []contract.Primitive) bool {
	for _, parent := range parents {
		if p.ID == parent.ID {
			return true
		}
	}
	return false
}

func containingRasterParentID(p contract.Primitive, parents []contract.Primitive) string {
	for _, parent := range parents {
		if parent.ID == p.ID {
			continue
		}
		if contains(parent.BBox, p.BBox, 3) {
			return parent.ID
		}
	}
	return ""
}

func containingSurfaceParentID(p contract.Primitive, parents []contract.Primitive) string {
	if p.PrimitiveType == "surface_region" {
		return ""
	}
	for _, parent := range parents {
		if parent.ID == p.ID {
			continue
		}
		if contains(parent.BBox, p.BBox, 3) {
			return parent.ID
		}
	}
	return ""
}

func clusterSymbols(primitives []contract.Primitive, consumed map[string]bool) [][]contract.Primitive {
	var symbols []contract.Primitive
	for _, p := range primitives {
		if consumed[p.ID] || p.PrimitiveType != "symbol_region" {
			continue
		}
		symbols = append(symbols, p)
	}
	visited := map[string]bool{}
	var clusters [][]contract.Primitive
	for _, seed := range symbols {
		if visited[seed.ID] {
			continue
		}
		cluster := []contract.Primitive{seed}
		visited[seed.ID] = true
		changed := true
		for changed {
			changed = false
			box := unionBBox(cluster)
			for _, candidate := range symbols {
				if visited[candidate.ID] {
					continue
				}
				if shouldJoinSymbolCluster(box, candidate) {
					cluster = append(cluster, candidate)
					visited[candidate.ID] = true
					changed = true
				}
			}
		}
		clusters = append(clusters, cluster)
	}
	return clusters
}

func shouldJoinSymbolCluster(box contract.BBox, candidate contract.Primitive) bool {
	if area(candidate.BBox) > 16000 {
		return false
	}
	if area(box) > 36000 {
		return false
	}
	return bboxDistance(box, candidate.BBox) <= 10
}

func tokenTypeForPrimitive(p contract.Primitive) string {
	switch p.PrimitiveType {
	case "rect":
		return "layer_background_token"
	case "surface_region":
		return "surface_region_token"
	case "line":
		return "line_token"
	case "image_region":
		return "raster_region_token"
	case "symbol_region":
		return "symbol_cluster_token"
	case "unknown_region":
		return "unknown_token"
	default:
		return "unknown_token"
	}
}

func tokenFromPrimitive(index int, tokenType string, p contract.Primitive, disposition string, reasons []string) Token {
	token := Token{
		ID:                 fmt.Sprintf("token_%04d", index),
		TokenType:          tokenType,
		BBox:               p.BBox,
		SourcePrimitiveIDs: []string{p.ID},
		Measurements: TokenMeasurements{
			Area:                  area(p.BBox),
			PrimitiveCount:        1,
			MeanColor:             p.Measurements.MeanColor,
			TextureScore:          p.Measurements.TextureScore,
			OriginalPrimitiveType: p.PrimitiveType,
		},
		Disposition:  disposition,
		Reasons:      reasons,
		CompileHints: p.CompileHints,
	}
	if tokenType == "text_token" {
		token.Content.Text = p.Source.Text
	}
	return token
}

func tokenFromCluster(index int, primitives []contract.Primitive) Token {
	box := unionBBox(primitives)
	ids := make([]string, 0, len(primitives))
	maxChildArea := 0
	childAreaSum := 0
	for _, p := range primitives {
		ids = append(ids, p.ID)
		childArea := area(p.BBox)
		childAreaSum += childArea
		if childArea > maxChildArea {
			maxChildArea = childArea
		}
	}
	sort.Strings(ids)
	disposition, reasons := clusterDisposition(box, len(primitives), childAreaSum)
	return Token{
		ID:                 fmt.Sprintf("token_%04d", index),
		TokenType:          "symbol_cluster_token",
		BBox:               box,
		SourcePrimitiveIDs: ids,
		Measurements: TokenMeasurements{
			Area:                  area(box),
			PrimitiveCount:        len(primitives),
			MaxChildAreaRatio:     round4(float64(maxChildArea) / float64(max(1, area(box)))),
			OriginalPrimitiveType: "symbol_region",
		},
		Disposition: disposition,
		Reasons:     reasons,
		CompileHints: contract.CompileHints{
			CanBeIcon:  disposition == "main",
			Confidence: clusterConfidence(disposition),
			Reasons:    reasons,
		},
	}
}

func clusterDisposition(box contract.BBox, primitiveCount int, childAreaSum int) (string, []string) {
	reasons := []string{"nearby_symbol_region_cluster"}
	boxArea := max(1, area(box))
	density := float64(childAreaSum) / float64(boxArea)
	aspect := float64(max(box.Width, box.Height)) / float64(max(1, min(box.Width, box.Height)))
	if box.Width > 180 || box.Height > 180 || boxArea > 22000 {
		reasons = append(reasons, "oversized_symbol_cluster_review")
		return "review", reasons
	}
	if aspect > 5.5 && max(box.Width, box.Height) > 80 {
		reasons = append(reasons, "high_aspect_symbol_cluster_review")
		return "review", reasons
	}
	if primitiveCount >= 4 && density < 0.08 && boxArea > 2400 {
		reasons = append(reasons, "low_density_symbol_cluster_review")
		return "review", reasons
	}
	return "main", reasons
}

func clusterConfidence(disposition string) float64 {
	if disposition == "main" {
		return 0.62
	}
	return 0.32
}

func buildDiagnostics(source contract.Document, tokens []Token) Diagnostics {
	counts := map[string]int{}
	suppressed := 0
	main := 0
	review := 0
	clustered := 0
	text := 0
	raster := 0
	surface := 0
	oversizedCluster := 0
	lowDensityCluster := 0
	highAspectCluster := 0
	for _, token := range tokens {
		counts[token.TokenType]++
		switch token.Disposition {
		case "main":
			main++
		case "review":
			review++
		case "suppressed":
			suppressed++
		}
		if token.Measurements.PrimitiveCount > 1 {
			clustered += token.Measurements.PrimitiveCount
		}
		if token.TokenType == "text_token" {
			text++
		}
		if token.TokenType == "raster_region_token" {
			raster++
		}
		if token.TokenType == "surface_region_token" {
			surface++
		}
		if hasReason(token, "oversized_symbol_cluster_review") {
			oversizedCluster++
		}
		if hasReason(token, "low_density_symbol_cluster_review") {
			lowDensityCluster++
		}
		if hasReason(token, "high_aspect_symbol_cluster_review") {
			highAspectCluster++
		}
	}
	return Diagnostics{
		TokenCount:                   len(tokens),
		TokenTypeCounts:              counts,
		PrimitiveCount:               len(source.Primitives),
		MainTokenCount:               main,
		ReviewTokenCount:             review,
		SuppressedCount:              suppressed,
		ClusteredCount:               clustered,
		TextTokenCount:               text,
		RasterTokenCount:             raster,
		SurfaceTokenCount:            surface,
		OversizedClusterReviewCount:  oversizedCluster,
		LowDensityClusterReviewCount: lowDensityCluster,
		HighAspectClusterReviewCount: highAspectCluster,
	}
}

func hasReason(token Token, reason string) bool {
	for _, item := range token.Reasons {
		if item == reason {
			return true
		}
	}
	return false
}

func unionBBox(items []contract.Primitive) contract.BBox {
	if len(items) == 0 {
		return contract.BBox{}
	}
	x1 := items[0].BBox.X
	y1 := items[0].BBox.Y
	x2 := items[0].BBox.X + items[0].BBox.Width
	y2 := items[0].BBox.Y + items[0].BBox.Height
	for _, item := range items[1:] {
		x1 = min(x1, item.BBox.X)
		y1 = min(y1, item.BBox.Y)
		x2 = max(x2, item.BBox.X+item.BBox.Width)
		y2 = max(y2, item.BBox.Y+item.BBox.Height)
	}
	return contract.BBox{X: x1, Y: y1, Width: x2 - x1, Height: y2 - y1}
}

func contains(parent, child contract.BBox, tolerance int) bool {
	return parent.X-tolerance <= child.X &&
		parent.Y-tolerance <= child.Y &&
		parent.X+parent.Width+tolerance >= child.X+child.Width &&
		parent.Y+parent.Height+tolerance >= child.Y+child.Height
}

func bboxDistance(a, b contract.BBox) int {
	ax2, ay2 := a.X+a.Width, a.Y+a.Height
	bx2, by2 := b.X+b.Width, b.Y+b.Height
	dx := max(max(b.X-ax2, a.X-bx2), 0)
	dy := max(max(b.Y-ay2, a.Y-by2), 0)
	if dx > dy {
		return dx
	}
	return dy
}

func area(b contract.BBox) int {
	return max(0, b.Width) * max(0, b.Height)
}

func round4(value float64) float64 {
	return float64(int(value*10000+0.5)) / 10000
}
