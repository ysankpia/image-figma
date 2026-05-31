package canvas

import (
	"encoding/json"
	"fmt"
	"os"
	"sort"
	"strconv"
	"strings"
)

const (
	analysisSchemaName = "CodiaCanvasAnalysis"
	analysisVersion    = "1.0"
	schemaPluginKey    = "schema:id"
)

var expectedRoleMapping = map[string]struct {
	Type string
	Name string
}{
	"root":             {Type: "FRAME", Name: "Root"},
	"ViewGroup":        {Type: "FRAME", Name: "Groups"},
	"ListView":         {Type: "FRAME", Name: "Groups"},
	"ActionBar":        {Type: "FRAME", Name: "Groups"},
	"StatusBar":        {Type: "FRAME", Name: "Groups"},
	"BottomNavigation": {Type: "FRAME", Name: "Groups"},
	"Button":           {Type: "FRAME", Name: "Button"},
	"EditText":         {Type: "FRAME", Name: "Text"},
	"TextView":         {Type: "TEXT"},
	"ImageView":        {Type: "ROUNDED_RECTANGLE", Name: "Image"},
	"Background":       {Type: "ROUNDED_RECTANGLE", Name: "Background"},
	"bg_Button":        {Type: "ROUNDED_RECTANGLE", Name: "Background"},
	"bg_EditText":      {Type: "ROUNDED_RECTANGLE", Name: "Background"},
}

func AnalyzeFile(path string, expectation string) (Analysis, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return Analysis{}, err
	}
	var doc CanvasDocument
	if err := json.Unmarshal(data, &doc); err != nil {
		return Analysis{}, err
	}
	analysis, err := Analyze(doc, path, expectation)
	if err != nil {
		return Analysis{}, err
	}
	return analysis, nil
}

func Analyze(doc CanvasDocument, inputPath string, expectation string) (Analysis, error) {
	design, designPath := findDesignFrame(&doc.Root, "")
	if design == nil {
		return Analysis{}, fmt.Errorf("cannot find Figma design frame")
	}
	root, rootPath := findNamedChild(design, designPath, "Root")
	if root == nil {
		root, rootPath = findSchemaRoleChild(design, designPath, "root")
	}
	if root == nil {
		return Analysis{}, fmt.Errorf("cannot find Root or schema root under %q", design.Name)
	}

	nodes := make([]*NodeFact, 0)
	rootFact := buildNodeFacts(root, rootPath, "", nil, 0, 0, 0, &nodes)
	analysis := Analysis{
		SchemaName:      analysisSchemaName,
		Version:         analysisVersion,
		InputPath:       inputPath,
		CanvasVersion:   doc.Version,
		DesignFramePath: designPath,
		DesignFrameName: design.Name,
		RootPath:        rootPath,
		RootName:        root.Name,
		RootBBox:        rootFact.BBox,
		RootChildCount:  len(rootFact.Children),
		NodeCount:       len(nodes),
		TypeCounts:      map[string]int{},
		NameCounts:      map[string]int{},
		RoleCounts:      map[string]int{},
		LastChild:       map[string]LastChildReport{},
		ButtonModes:     map[string]int{},
		EditTextModes:   map[string]int{},
		Expectation:     expectation,
		Nodes:           make([]NodeFact, 0, len(nodes)),
	}
	for _, node := range nodes {
		analysis.TypeCounts[node.Type]++
		analysis.NameCounts[node.Name]++
		if node.Role != "" {
			analysis.RoleCounts[node.Role]++
		}
		if node.GUID != "" {
			analysis.GUIDCoverage.Present++
		}
		if node.SchemaID != "" {
			analysis.SchemaCoverage.Present++
		}
		if node.Depth > analysis.MaxDepth {
			analysis.MaxDepth = node.Depth
		}
		analysis.Nodes = append(analysis.Nodes, *node)
	}
	analysis.GUIDCoverage.Total = len(nodes)
	analysis.SchemaCoverage.Total = len(nodes)
	analysis.Suffix = buildSuffixReport(nodes)
	analysis.ChildOrder = buildChildOrderReport(nodes)
	analysis.LastChild["Background"] = buildLastChildReport(nodes, "Background")
	analysis.LastChild["bg_Button"] = buildLastChildReport(nodes, "bg_Button")
	analysis.LastChild["bg_EditText"] = buildLastChildReport(nodes, "bg_EditText")
	analysis.ButtonModes = buildControlModes(nodes, "Button")
	analysis.EditTextModes = buildControlModes(nodes, "EditText")
	analysis.Text = buildTextReport(nodes)
	analysis.ImageFills = buildImageFillReport(nodes)
	analysis.CornerRadius = buildCornerRadiusReport(nodes)
	analysis.Overflow = buildOverflowReport(nodes)
	analysis.SiblingOverlap = buildSiblingOverlapReport(nodes)
	analysis.RoleMappingViolations = buildRoleMappingViolations(nodes)
	if expectation != "" {
		analysis.ExpectationFailures = CheckExpectation(analysis, expectation)
	}
	sortNodeFacts(analysis.Nodes)
	return analysis, nil
}

func findDesignFrame(node *CanvasNode, path string) (*CanvasNode, string) {
	if node != nil && strings.HasPrefix(node.Name, "Figma design -") {
		return node, path
	}
	for i := range node.Children {
		childPath := childPath(path, i)
		if found, foundPath := findDesignFrame(&node.Children[i], childPath); found != nil {
			return found, foundPath
		}
	}
	return nil, ""
}

func findNamedChild(node *CanvasNode, path string, name string) (*CanvasNode, string) {
	for i := range node.Children {
		child := &node.Children[i]
		childPath := childPath(path, i)
		if child.Name == name {
			return child, childPath
		}
		if found, foundPath := findNamedChild(child, childPath, name); found != nil {
			return found, foundPath
		}
	}
	return nil, ""
}

func findSchemaRoleChild(node *CanvasNode, path string, role string) (*CanvasNode, string) {
	for i := range node.Children {
		child := &node.Children[i]
		childPath := childPath(path, i)
		if parseSchemaID(schemaID(child)).Role == role {
			return child, childPath
		}
		if found, foundPath := findSchemaRoleChild(child, childPath, role); found != nil {
			return found, foundPath
		}
	}
	return nil, ""
}

func childPath(path string, index int) string {
	if path == "" {
		return "/" + strconv.Itoa(index)
	}
	return path + "/" + strconv.Itoa(index)
}

func buildNodeFacts(
	node *CanvasNode,
	path string,
	parentPath string,
	parent *NodeFact,
	depth int,
	parentAbsX int,
	parentAbsY int,
	nodes *[]*NodeFact,
) *NodeFact {
	x := parentAbsX + roundInt(node.Transform.M02)
	y := parentAbsY + roundInt(node.Transform.M12)
	schema := parseSchemaID(schemaID(node))
	fact := &NodeFact{
		Path:           path,
		ParentPath:     parentPath,
		GUID:           guidString(node.GUID),
		Type:           node.Type,
		Name:           node.Name,
		Role:           schema.Role,
		SchemaID:       schema.Raw,
		SchemaX:        schema.X,
		SchemaY:        schema.Y,
		SchemaSeq:      schema.Seq,
		HasSchemaSeq:   schema.Valid,
		BBox:           BBox{X: x, Y: y, Width: roundInt(node.Size.X), Height: roundInt(node.Size.Y)},
		Depth:          depth,
		ChildCount:     len(node.Children),
		TextCharacters: textCharacters(node),
		FillTypes:      fillTypes(node),
		ImageHashes:    imageHashes(node),
		CornerRadius:   cornerRadius(node),
		Source:         node,
		Parent:         parent,
		Schema:         schema,
	}
	*nodes = append(*nodes, fact)
	for i := range node.Children {
		childPathValue := childPath(path, i)
		child := buildNodeFacts(&node.Children[i], childPathValue, path, fact, depth+1, x, y, nodes)
		fact.Children = append(fact.Children, child)
		fact.ChildRoles = append(fact.ChildRoles, child.Role)
		fact.ChildSchemaIDs = append(fact.ChildSchemaIDs, child.SchemaID)
	}
	return fact
}

func schemaID(node *CanvasNode) string {
	for _, datum := range node.PluginData {
		if datum.Key == schemaPluginKey {
			return datum.Value
		}
	}
	return ""
}

func parseSchemaID(value string) SchemaIDInfo {
	if value == "" {
		return SchemaIDInfo{}
	}
	parts := strings.Split(value, "_")
	if len(parts) == 2 && parts[0] == "root" {
		seq, err := strconv.Atoi(parts[1])
		return SchemaIDInfo{Raw: value, Role: "root", Seq: seq, Valid: err == nil}
	}
	if len(parts) < 4 {
		return SchemaIDInfo{Raw: value, Role: parts[0]}
	}
	seq, seqErr := strconv.Atoi(parts[len(parts)-1])
	y, yErr := strconv.Atoi(parts[len(parts)-2])
	x, xErr := strconv.Atoi(parts[len(parts)-3])
	role := strings.Join(parts[:len(parts)-3], "_")
	return SchemaIDInfo{
		Raw:   value,
		Role:  role,
		X:     x,
		Y:     y,
		Seq:   seq,
		Valid: seqErr == nil && yErr == nil && xErr == nil && role != "",
	}
}

func buildSuffixReport(nodes []*NodeFact) SuffixReport {
	report := SuffixReport{Min: 0, Max: -1}
	counts := map[int]int{}
	for _, node := range nodes {
		if !node.HasSchemaSeq {
			continue
		}
		report.Present++
		if report.Max == -1 || node.SchemaSeq < report.Min {
			report.Min = node.SchemaSeq
		}
		if node.SchemaSeq > report.Max {
			report.Max = node.SchemaSeq
		}
		counts[node.SchemaSeq]++
	}
	for seq, count := range counts {
		if count > 1 {
			report.Duplicates = append(report.Duplicates, seq)
		}
	}
	sort.Ints(report.Duplicates)
	if report.Present > 0 {
		for seq := report.Min; seq <= report.Max; seq++ {
			if counts[seq] == 0 {
				report.Missing = append(report.Missing, seq)
			}
		}
	}
	return report
}

func buildChildOrderReport(nodes []*NodeFact) ChildOrderReport {
	report := ChildOrderReport{}
	for _, node := range nodes {
		if len(node.Children) <= 1 {
			continue
		}
		report.MultiChildParents++
		descending := true
		seqs := make([]int, 0, len(node.Children))
		childSchemas := make([]string, 0, len(node.Children))
		for _, child := range node.Children {
			seqs = append(seqs, child.SchemaSeq)
			childSchemas = append(childSchemas, child.SchemaID)
		}
		for i := 0; i < len(node.Children)-1; i++ {
			if !node.Children[i].HasSchemaSeq || !node.Children[i+1].HasSchemaSeq || node.Children[i].SchemaSeq <= node.Children[i+1].SchemaSeq {
				descending = false
				break
			}
		}
		if descending {
			report.StrictDescendingParents++
			continue
		}
		report.Violations = append(report.Violations, ChildOrderViolation{
			Path:     node.Path,
			SchemaID: node.SchemaID,
			Children: childSchemas,
			Seqs:     seqs,
		})
	}
	return report
}

func buildLastChildReport(nodes []*NodeFact, role string) LastChildReport {
	report := LastChildReport{}
	for _, node := range nodes {
		if node.Role != role {
			continue
		}
		report.Total++
		if node.Parent != nil && len(node.Parent.Children) > 0 && node.Parent.Children[len(node.Parent.Children)-1] == node {
			report.Last++
			continue
		}
		report.NotLast = append(report.NotLast, node.Path)
	}
	return report
}

func buildControlModes(nodes []*NodeFact, role string) map[string]int {
	modes := map[string]int{}
	for _, node := range nodes {
		if node.Role != role {
			continue
		}
		roles := make([]string, 0, len(node.Children))
		for _, child := range node.Children {
			roles = append(roles, child.Role)
		}
		modes[strings.Join(roles, "+")]++
	}
	return modes
}

func buildTextReport(nodes []*NodeFact) TextReport {
	report := TextReport{
		FontCounts:         map[string]int{},
		AutoResizeCounts:   map[string]int{},
		LineHeightCounts:   map[string]int{},
		AlignVerticalCount: map[string]int{},
	}
	var sizes []int
	for _, node := range nodes {
		if node.Role != "TextView" {
			continue
		}
		report.TextViewCount++
		if node.Name == node.TextCharacters {
			report.NameCharacterMatch++
		} else {
			report.Mismatches = append(report.Mismatches, TextMismatch{
				Path:       node.Path,
				SchemaID:   node.SchemaID,
				Name:       node.Name,
				Characters: node.TextCharacters,
			})
		}
		fontKey := fontKey(node.Source.FontName)
		if fontKey != "" {
			report.FontCounts[fontKey]++
		}
		if node.Source.FontSize > 0 {
			sizes = append(sizes, roundInt(node.Source.FontSize))
		}
		autoResize := node.Source.TextAutoResize
		if autoResize == "" {
			autoResize = "<missing>"
		}
		report.AutoResizeCounts[autoResize]++
		report.AlignVerticalCount[node.Source.TextAlignVertical]++
		if node.Source.LineHeight != nil {
			report.LineHeightCounts[fmt.Sprintf("%g %s", node.Source.LineHeight.Value, node.Source.LineHeight.Units)]++
		} else {
			report.LineHeightCounts["<missing>"]++
		}
	}
	if len(sizes) > 0 {
		sort.Ints(sizes)
		report.FontSizeMin = sizes[0]
		report.FontSizeMax = sizes[len(sizes)-1]
		report.FontSizeMedian = sizes[len(sizes)/2]
	}
	return report
}

func buildImageFillReport(nodes []*NodeFact) ImageFillReport {
	unique := map[string]bool{}
	count := 0
	for _, node := range nodes {
		for i, fillType := range node.FillTypes {
			if fillType != "IMAGE" {
				continue
			}
			count++
			if i < len(node.ImageHashes) && node.ImageHashes[i] != "" {
				unique[node.ImageHashes[i]] = true
			}
		}
	}
	return ImageFillReport{ImageFillCount: count, UniqueHashCount: len(unique)}
}

func buildCornerRadiusReport(nodes []*NodeFact) CornerRadiusReport {
	report := CornerRadiusReport{ByRole: map[string]int{}}
	for _, node := range nodes {
		if node.CornerRadius == nil {
			continue
		}
		report.NodeCount++
		report.ByRole[node.Role]++
	}
	return report
}

func buildOverflowReport(nodes []*NodeFact) OverflowReport {
	report := OverflowReport{}
	for _, node := range nodes {
		if node.Parent == nil {
			continue
		}
		parent := node.Parent
		left := node.BBox.X - parent.BBox.X
		top := node.BBox.Y - parent.BBox.Y
		right := (parent.BBox.X + parent.BBox.Width) - (node.BBox.X + node.BBox.Width)
		bottom := (parent.BBox.Y + parent.BBox.Height) - (node.BBox.Y + node.BBox.Height)
		if left >= 0 && top >= 0 && right >= 0 && bottom >= 0 {
			continue
		}
		report.Count++
		report.Items = append(report.Items, OverflowItem{
			Path:           node.Path,
			SchemaID:       node.SchemaID,
			ParentPath:     parent.Path,
			ParentSchemaID: parent.SchemaID,
			DeltaLeft:      left,
			DeltaTop:       top,
			DeltaRight:     right,
			DeltaBottom:    bottom,
		})
	}
	return report
}

func buildSiblingOverlapReport(nodes []*NodeFact) SiblingOverlapReport {
	report := SiblingOverlapReport{ByParent: map[string]int{}}
	for _, parent := range nodes {
		if len(parent.Children) <= 1 {
			continue
		}
		for i := 0; i < len(parent.Children); i++ {
			for j := i + 1; j < len(parent.Children); j++ {
				intersection := intersectionArea(parent.Children[i].BBox, parent.Children[j].BBox)
				if intersection <= 0 {
					continue
				}
				report.PairCount++
				report.ByParent[parent.Path]++
				if len(report.Samples) < 50 {
					report.Samples = append(report.Samples, SiblingOverlapItem{
						ParentPath:     parent.Path,
						ParentSchemaID: parent.SchemaID,
						LeftPath:       parent.Children[i].Path,
						LeftSchemaID:   parent.Children[i].SchemaID,
						RightPath:      parent.Children[j].Path,
						RightSchemaID:  parent.Children[j].SchemaID,
						Intersection:   intersection,
					})
				}
			}
		}
	}
	return report
}

func buildRoleMappingViolations(nodes []*NodeFact) []RoleMappingViolation {
	var out []RoleMappingViolation
	for _, node := range nodes {
		expected, ok := expectedRoleMapping[node.Role]
		if !ok {
			out = append(out, RoleMappingViolation{
				Path:     node.Path,
				SchemaID: node.SchemaID,
				Role:     node.Role,
				Type:     node.Type,
				Name:     node.Name,
				Reason:   "unknown_role",
			})
			continue
		}
		if expected.Type != "" && node.Type != expected.Type {
			out = append(out, RoleMappingViolation{
				Path:     node.Path,
				SchemaID: node.SchemaID,
				Role:     node.Role,
				Type:     node.Type,
				Name:     node.Name,
				Reason:   "type_mismatch",
			})
		}
		if node.Role == "TextView" {
			if node.Name != node.TextCharacters {
				out = append(out, RoleMappingViolation{
					Path:       node.Path,
					SchemaID:   node.SchemaID,
					Role:       node.Role,
					Type:       node.Type,
					Name:       node.Name,
					Characters: node.TextCharacters,
					Reason:     "text_name_character_mismatch",
				})
			}
			continue
		}
		if expected.Name != "" && node.Name != expected.Name {
			out = append(out, RoleMappingViolation{
				Path:     node.Path,
				SchemaID: node.SchemaID,
				Role:     node.Role,
				Type:     node.Type,
				Name:     node.Name,
				Reason:   "name_mismatch",
			})
		}
	}
	return out
}

func sortNodeFacts(nodes []NodeFact) {
	sort.SliceStable(nodes, func(i, j int) bool {
		return nodes[i].Path < nodes[j].Path
	})
}

func guidString(guid *GUID) string {
	if guid == nil {
		return ""
	}
	return fmt.Sprintf("%d:%d", guid.SessionID, guid.LocalID)
}

func textCharacters(node *CanvasNode) string {
	if node.TextData == nil {
		return ""
	}
	return node.TextData.Characters
}

func fillTypes(node *CanvasNode) []string {
	out := make([]string, 0, len(node.FillPaints))
	for _, paint := range node.FillPaints {
		out = append(out, paint.Type)
	}
	return out
}

func imageHashes(node *CanvasNode) []string {
	out := make([]string, 0, len(node.FillPaints))
	for _, paint := range node.FillPaints {
		hash := ""
		if paint.Image != nil && len(paint.Image.Hash) > 0 {
			hash = hashString(paint.Image.Hash)
		} else if paint.ImageThumbnail != nil && len(paint.ImageThumbnail.Hash) > 0 {
			hash = hashString(paint.ImageThumbnail.Hash)
		}
		out = append(out, hash)
	}
	return out
}

func cornerRadius(node *CanvasNode) *CornerRadius {
	if node.RectTopLeftRadius == nil &&
		node.RectTopRightRadius == nil &&
		node.RectBottomLeftRadius == nil &&
		node.RectBottomRightRadius == nil &&
		!node.RectRadiiIndependent {
		return nil
	}
	return &CornerRadius{
		TopLeft:     floatValue(node.RectTopLeftRadius),
		TopRight:    floatValue(node.RectTopRightRadius),
		BottomLeft:  floatValue(node.RectBottomLeftRadius),
		BottomRight: floatValue(node.RectBottomRightRadius),
		Independent: node.RectRadiiIndependent,
	}
}

func floatValue(value *float64) float64 {
	if value == nil {
		return 0
	}
	return *value
}

func hashString(values []int) string {
	parts := make([]string, 0, len(values))
	for _, value := range values {
		parts = append(parts, strconv.Itoa(value))
	}
	return strings.Join(parts, ",")
}

func fontKey(font *FontName) string {
	if font == nil {
		return ""
	}
	if font.Style == "" {
		return font.Family
	}
	return font.Family + " " + font.Style
}

func intersectionArea(a, b BBox) int {
	x1 := max(a.X, b.X)
	y1 := max(a.Y, b.Y)
	x2 := min(a.X+a.Width, b.X+b.Width)
	y2 := min(a.Y+a.Height, b.Y+b.Height)
	if x2 <= x1 || y2 <= y1 {
		return 0
	}
	return (x2 - x1) * (y2 - y1)
}

func roundInt(value float64) int {
	if value < 0 {
		return int(value - 0.5)
	}
	return int(value + 0.5)
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}

func max(a, b int) int {
	if a > b {
		return a
	}
	return b
}
