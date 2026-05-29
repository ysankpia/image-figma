package visualtree

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/contract"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/evidence"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/relation"
)

type Options struct {
	TokenPath    string
	RelationPath string
	OutputDir    string
}

func Compile(options Options) (Document, error) {
	if options.TokenPath == "" {
		return Document{}, fmt.Errorf("missing token path")
	}
	if options.RelationPath == "" {
		return Document{}, fmt.Errorf("missing relation path")
	}
	if options.OutputDir == "" {
		return Document{}, fmt.Errorf("missing output dir")
	}
	tokens, err := readTokens(options.TokenPath)
	if err != nil {
		return Document{}, err
	}
	relations, err := readRelations(options.RelationPath)
	if err != nil {
		return Document{}, err
	}
	root, diagnostics, containmentReport, trace := buildTree(tokens, relations)
	source := Source{
		TokenSchemaName:    tokens.SchemaName,
		TokenVersion:       tokens.Version,
		RelationSchemaName: relations.SchemaName,
		RelationVersion:    relations.Version,
		ImageWidth:         tokens.Source.ImageWidth,
		ImageHeight:        tokens.Source.ImageHeight,
		SourcePath:         tokens.Source.SourcePath,
		TokenCount:         len(tokens.Tokens),
		RelationCount:      len(relations.Relations),
	}
	doc := Document{
		SchemaName:        "M29VisualTree",
		Version:           "1.0",
		Source:            source,
		Root:              root,
		VisualElement:     buildVisualElement(root),
		Diagnostics:       diagnostics,
		ContainmentReport: containmentReport,
	}
	if err := os.MkdirAll(options.OutputDir, 0o755); err != nil {
		return Document{}, err
	}
	data, err := json.MarshalIndent(doc, "", "  ")
	if err != nil {
		return Document{}, err
	}
	if err := os.WriteFile(filepath.Join(options.OutputDir, "visual_tree.v1.json"), data, 0o644); err != nil {
		return Document{}, err
	}
	visualElementDoc := VisualElementDocument{
		SchemaName:    "M29VisualElement",
		Version:       "1.0",
		Source:        source,
		VisualElement: doc.VisualElement,
		Diagnostics:   diagnostics,
	}
	visualElementData, err := json.MarshalIndent(visualElementDoc, "", "  ")
	if err != nil {
		return Document{}, err
	}
	if err := os.WriteFile(filepath.Join(options.OutputDir, "visual_element.v1.json"), visualElementData, 0o644); err != nil {
		return Document{}, err
	}
	if err := writeTraceArtifacts(options.OutputDir, root, trace); err != nil {
		return Document{}, err
	}
	if err := writeArtifacts(options.OutputDir, tokens.Source.SourcePath, doc); err != nil {
		return Document{}, err
	}
	return doc, nil
}

func readTokens(path string) (evidence.Document, error) {
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

func readRelations(path string) (relation.Document, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return relation.Document{}, err
	}
	var doc relation.Document
	if err := json.Unmarshal(data, &doc); err != nil {
		return relation.Document{}, err
	}
	if doc.SchemaName != "M29RelationGraph" {
		return relation.Document{}, fmt.Errorf("expected M29RelationGraph, got %q", doc.SchemaName)
	}
	return doc, nil
}

func buildTree(tokens evidence.Document, relations relation.Document) (Node, Diagnostics, ContainmentReport, *TraceRecorder) {
	trace := NewTraceRecorder()
	tokenByID := map[string]evidence.Token{}
	skipped := 0
	for _, token := range tokens.Tokens {
		if token.Disposition == "suppressed" {
			skipped++
			continue
		}
		if token.BBox.Width <= 0 || token.BBox.Height <= 0 {
			skipped++
			continue
		}
		tokenByID[token.ID] = token
	}
	trace.Record(TraceEvent{
		Operation:     "token_filter_summary",
		Decision:      "record",
		DecisionClass: "diagnostic",
		Reason:        "filter_suppressed_or_invalid_bbox_tokens",
		Metrics: map[string]any{
			"inputTokenCount":   len(tokens.Tokens),
			"activeTokenCount":  len(tokenByID),
			"skippedTokenCount": skipped,
			"relationCount":     len(relations.Relations),
			"sourceImageWidth":  tokens.Source.ImageWidth,
			"sourceImageHeight": tokens.Source.ImageHeight,
		},
	})
	childrenByParent := map[string][]string{}
	relationIDsByChild := map[string][]string{}
	for _, rel := range relations.Relations {
		if rel.RelationType != "contains" {
			continue
		}
		parent, okParent := tokenByID[rel.FromID]
		child, okChild := tokenByID[rel.ToID]
		if !okParent || !okChild {
			continue
		}
		if !canContain(parent) || parent.ID == child.ID {
			continue
		}
		childrenByParent[parent.ID] = append(childrenByParent[parent.ID], child.ID)
		relationIDsByChild[child.ID] = append(relationIDsByChild[child.ID], rel.ID)
	}

	parentByChild := chooseSmallestParents(tokenByID, childrenByParent)
	directChildren := make([]string, 0, len(tokenByID))
	children := map[string][]string{}
	for id := range tokenByID {
		parentID := parentByChild[id]
		if parentID == "" {
			directChildren = append(directChildren, id)
			continue
		}
		children[parentID] = append(children[parentID], id)
	}
	sortTokenIDs(directChildren, tokenByID)
	for parentID := range children {
		sortTokenIDs(children[parentID], tokenByID)
	}

	root := Node{
		ID:   "body_0001",
		Type: "Body",
		Name: "Body",
		BBox: contract.BBox{X: 0, Y: 0, Width: tokens.Source.ImageWidth, Height: tokens.Source.ImageHeight},
		Layout: Layout{
			Mode:     "absolute",
			X:        0,
			Y:        0,
			Width:    tokens.Source.ImageWidth,
			Height:   tokens.Source.ImageHeight,
			Relative: false,
		},
	}
	for _, childID := range directChildren {
		root.Children = append(root.Children, buildNode(childID, "", tokenByID, children, relationIDsByChild))
	}
	groupCounter := 1
	containmentReport := applyContainmentTree(&root, relations.Relations, tokenByID, trace)
	materializePhysicalBackgroundLeaves(&root, tokenByID, trace)
	applySpatialGrouping(&root, &groupCounter, trace)
	refreshTreeLayouts(&root)
	diagnostics := buildDiagnostics(tokens, relations, root, parentByChild, skipped, containmentReport)
	return root, diagnostics, containmentReport, trace
}

func chooseSmallestParents(tokens map[string]evidence.Token, childrenByParent map[string][]string) map[string]string {
	parentByChild := map[string]string{}
	for parentID, childIDs := range childrenByParent {
		parent := tokens[parentID]
		for _, childID := range childIDs {
			currentID := parentByChild[childID]
			if currentID == "" || area(parent.BBox) < area(tokens[currentID].BBox) {
				parentByChild[childID] = parentID
			}
		}
	}
	return parentByChild
}

func buildNode(
	tokenID string,
	parentID string,
	tokens map[string]evidence.Token,
	children map[string][]string,
	relationIDsByChild map[string][]string,
) Node {
	token := tokens[tokenID]
	nodeType := nodeTypeForToken(token, len(children[tokenID]) > 0)
	node := Node{
		ID:   token.ID,
		Type: nodeType,
		Name: nodeType + " / " + token.ID,
		BBox: token.BBox,
		Layout: Layout{
			Mode:     "absolute",
			X:        token.BBox.X,
			Y:        token.BBox.Y,
			Width:    token.BBox.Width,
			Height:   token.BBox.Height,
			Relative: parentID != "",
		},
		SourceRefs: SourceRefs{
			TokenIDs:    []string{token.ID},
			RelationIDs: append([]string(nil), relationIDsByChild[token.ID]...),
		},
	}
	if parentID != "" {
		parent := tokens[parentID]
		node.Layout.X = token.BBox.X - parent.BBox.X
		node.Layout.Y = token.BBox.Y - parent.BBox.Y
	}
	if node.Type == "Text" {
		node.Content.Text = token.Content.Text
	}
	if token.TokenType == "raster_region_token" && node.Type == "Layer" {
		node.Style.BackgroundRef = token.ID
		node.SourceRefs.BackgroundIDs = []string{token.ID}
	}
	for _, childID := range children[tokenID] {
		node.Children = append(node.Children, buildNode(childID, tokenID, tokens, children, relationIDsByChild))
	}
	return node
}

func nodeTypeForToken(token evidence.Token, hasChildren bool) string {
	switch token.TokenType {
	case "text_token":
		return "Text"
	case "surface_region_token", "layer_background_token":
		return "Layer"
	case "raster_region_token":
		if hasChildren && token.CompileHints.CanContainForeground {
			return "Layer"
		}
		return "Image"
	default:
		return "Image"
	}
}

func canContain(token evidence.Token) bool {
	switch token.TokenType {
	case "surface_region_token", "layer_background_token":
		return true
	case "raster_region_token":
		return token.CompileHints.CanContainForeground
	default:
		return false
	}
}

func addPhysicalBackgroundLeaf(node *Node, token evidence.Token, trace *TraceRecorder) {
	if node.Type != "Layer" || !physicalLayerBackgroundToken(token) {
		return
	}
	bg := Node{
		ID:   node.ID + "_background",
		Type: "Image",
		Name: "Background / " + node.ID,
		BBox: token.BBox,
		Layout: Layout{
			Mode:     "absolute",
			X:        0,
			Y:        0,
			Width:    token.BBox.Width,
			Height:   token.BBox.Height,
			Relative: true,
		},
		SourceRefs: SourceRefs{
			TokenIDs:      []string{token.ID},
			BackgroundIDs: []string{token.ID},
		},
		Meta: Meta{
			Synthetic:    true,
			GroupKind:    "background_leaf",
			ParentReason: "physical_background",
		},
	}
	node.Style.BackgroundRef = token.ID
	node.SourceRefs.BackgroundIDs = []string{token.ID}
	node.Children = append([]Node{bg}, node.Children...)
	trace.Record(TraceEvent{
		Operation:     "physical_background_leaf_create",
		ParentNodeID:  node.ID,
		InputNodeIDs:  []string{node.ID, token.ID},
		OutputNodeIDs: []string{bg.ID},
		InputBBox:     &token.BBox,
		Decision:      "create_group",
		DecisionClass: "auxiliary",
		GroupKind:     "background_leaf",
		Reason:        "physical_background",
		SourceEvidence: map[string]any{
			"sourceTokenId": token.ID,
			"tokenType":     token.TokenType,
		},
	})
}

func materializePhysicalBackgroundLeaves(node *Node, tokens map[string]evidence.Token, trace *TraceRecorder) {
	if token, ok := singleSourceToken(*node, tokens); ok {
		addPhysicalBackgroundLeaf(node, token, trace)
	}
	for i := range node.Children {
		materializePhysicalBackgroundLeaves(&node.Children[i], tokens, trace)
	}
}

func physicalLayerBackgroundToken(token evidence.Token) bool {
	switch token.TokenType {
	case "surface_region_token", "layer_background_token":
		return true
	case "raster_region_token":
		return token.CompileHints.CanContainForeground
	default:
		return false
	}
}

func sortTokenIDs(ids []string, tokens map[string]evidence.Token) {
	sort.SliceStable(ids, func(i, j int) bool {
		a, b := tokens[ids[i]].BBox, tokens[ids[j]].BBox
		if a.Y != b.Y {
			return a.Y < b.Y
		}
		if a.X != b.X {
			return a.X < b.X
		}
		return ids[i] < ids[j]
	})
}

func buildDiagnostics(
	tokens evidence.Document,
	relations relation.Document,
	root Node,
	parentByChild map[string]string,
	skipped int,
	containmentReport ContainmentReport,
) Diagnostics {
	counts := map[string]int{}
	var walk func(Node)
	total := 0
	relative := 0
	backgroundLayers := 0
	syntheticGroups := 0
	groupKinds := map[string]int{}
	walk = func(node Node) {
		total++
		counts[node.Type]++
		if node.Layout.Relative {
			relative++
		}
		if node.Style.BackgroundRef != "" {
			backgroundLayers++
		}
		if node.Meta.Synthetic {
			syntheticGroups++
			groupKinds[node.Meta.GroupKind]++
		}
		for _, child := range node.Children {
			walk(child)
		}
	}
	walk(root)
	return Diagnostics{
		TokenCount:                  len(tokens.Tokens),
		RelationCount:               len(relations.Relations),
		NodeCount:                   total,
		BodyChildCount:              len(root.Children),
		NodeTypeCounts:              counts,
		ParentRelationCount:         len(parentByChild),
		SyntheticGroupCount:         syntheticGroups,
		GroupKindCounts:             groupKinds,
		BackgroundLayerCount:        backgroundLayers,
		ParentRelativeLayoutCount:   relative,
		SuppressedTokenSkippedCount: skipped,
		ContainmentCandidateCount:   containmentReport.CandidateCount,
		ContainmentAppliedCount:     containmentReport.AppliedCount,
		ContainmentOnlyParentCount:  containmentReport.ContainmentOnlyParentCount,
		RelationParentCount:         containmentReport.RelationParentCount,
		BodyChildCountBefore:        containmentReport.BodyChildCountBefore,
		BodyChildCountAfter:         containmentReport.BodyChildCountAfter,
	}
}

func area(b contract.BBox) int {
	return max(0, b.Width) * max(0, b.Height)
}

func max(a, b int) int {
	if a > b {
		return a
	}
	return b
}
