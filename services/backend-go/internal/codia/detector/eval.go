package detector

import (
	"encoding/json"
	"fmt"
	"os"
	"sort"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/ir"
)

type EvalOptions struct {
	CandidatesPath string
	GoldenPath     string
	OutputDir      string
}

type goldenNode struct {
	ID   string
	Role Role
	BBox BBox
}

func Eval(options EvalOptions) (EvalDocument, error) {
	if options.CandidatesPath == "" {
		return EvalDocument{}, fmt.Errorf("missing candidates path")
	}
	if options.GoldenPath == "" {
		return EvalDocument{}, fmt.Errorf("missing golden path")
	}
	candidates, err := ReadDocument(options.CandidatesPath)
	if err != nil {
		return EvalDocument{}, err
	}
	golden, err := readGoldenNodes(options.GoldenPath)
	if err != nil {
		return EvalDocument{}, err
	}
	doc := buildEval(candidates, golden)
	doc.Source.CandidatesPath = options.CandidatesPath
	doc.Source.GoldenPath = options.GoldenPath
	if options.OutputDir != "" {
		if err := WriteEvalArtifacts(options.OutputDir, doc); err != nil {
			return EvalDocument{}, err
		}
	}
	return doc, nil
}

func ReadDocument(path string) (Document, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return Document{}, err
	}
	var doc Document
	if err := json.Unmarshal(data, &doc); err != nil {
		return Document{}, err
	}
	if doc.Version != CandidatesVersion {
		return Document{}, fmt.Errorf("expected %s, got %q", CandidatesVersion, doc.Version)
	}
	return doc, nil
}

func readGoldenNodes(path string) ([]goldenNode, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var doc ir.Document
	if err := json.Unmarshal(data, &doc); err != nil {
		return nil, err
	}
	if doc.SchemaName != ir.SchemaName {
		return nil, fmt.Errorf("expected %s, got %q", ir.SchemaName, doc.SchemaName)
	}
	out := []goldenNode{}
	var walk func(ir.Node)
	walk = func(node ir.Node) {
		role := Role(node.Role)
		if allowedRole(role) {
			out = append(out, goldenNode{
				ID:   node.ID,
				Role: role,
				BBox: BBox{
					X:      float64(node.FigmaBBox.X),
					Y:      float64(node.FigmaBBox.Y),
					Width:  float64(node.FigmaBBox.Width),
					Height: float64(node.FigmaBBox.Height),
				},
			})
		}
		for _, child := range node.Children {
			walk(child)
		}
	}
	walk(doc.Root)
	return out, nil
}

func buildEval(candidates Document, golden []goldenNode) EvalDocument {
	roles := sortedEvalRoles(candidates.Candidates, golden)
	roleEvals := make([]RoleEval, 0, len(roles))
	totalMatched05 := 0
	totalMatched06 := 0
	extra := []EvalNode{}
	missed := []EvalNode{}
	for _, role := range roles {
		dets := filterCandidatesByRole(candidates.Candidates, role)
		golds := filterGoldenByRole(golden, role)
		m05, extra05, missed05 := matchRole(dets, golds, 0.5)
		m06, _, _ := matchRole(dets, golds, 0.6)
		totalMatched05 += len(m05)
		totalMatched06 += len(m06)
		for _, item := range extra05 {
			extra = append(extra, item)
		}
		for _, item := range missed05 {
			missed = append(missed, item)
		}
		roleEvals = append(roleEvals, RoleEval{
			Role:        role,
			Golden:      len(golds),
			Detector:    len(dets),
			MatchedAt05: len(m05),
			MatchedAt06: len(m06),
			Precision05: ratio(len(m05), len(dets)),
			Recall05:    ratio(len(m05), len(golds)),
			F105:        f1(ratio(len(m05), len(dets)), ratio(len(m05), len(golds))),
			Precision06: ratio(len(m06), len(dets)),
			Recall06:    ratio(len(m06), len(golds)),
			F106:        f1(ratio(len(m06), len(dets)), ratio(len(m06), len(golds))),
		})
	}
	sortEvalNodes(extra)
	sortEvalNodes(missed)
	return EvalDocument{
		Version: EvalVersion,
		Summary: EvalSummary{
			GoldenCount:    len(golden),
			DetectorCount:  len(candidates.Candidates),
			MatchedAt05:    totalMatched05,
			MatchedAt06:    totalMatched06,
			ExtraAt05:      len(extra),
			MissedAt05:     len(missed),
			MatchedRoleNum: matchedRoleCount(roleEvals),
		},
		Roles:  roleEvals,
		Extra:  extra,
		Missed: missed,
	}
}

type pair struct {
	DetIndex  int
	GoldIndex int
	Score     float64
}

func matchRole(dets []Candidate, golds []goldenNode, threshold float64) ([]pair, []EvalNode, []EvalNode) {
	pairs := []pair{}
	for i, det := range dets {
		for j, gold := range golds {
			score := iou(det.BBox, gold.BBox)
			if score >= threshold {
				pairs = append(pairs, pair{DetIndex: i, GoldIndex: j, Score: score})
			}
		}
	}
	sort.SliceStable(pairs, func(i, j int) bool {
		if pairs[i].Score != pairs[j].Score {
			return pairs[i].Score > pairs[j].Score
		}
		if pairs[i].DetIndex != pairs[j].DetIndex {
			return pairs[i].DetIndex < pairs[j].DetIndex
		}
		return pairs[i].GoldIndex < pairs[j].GoldIndex
	})
	usedDet := map[int]bool{}
	usedGold := map[int]bool{}
	matched := []pair{}
	for _, item := range pairs {
		if usedDet[item.DetIndex] || usedGold[item.GoldIndex] {
			continue
		}
		usedDet[item.DetIndex] = true
		usedGold[item.GoldIndex] = true
		matched = append(matched, item)
	}
	extra := []EvalNode{}
	for i, det := range dets {
		if usedDet[i] {
			continue
		}
		bestID, bestBBox, bestScore := bestGolden(det, golds)
		extra = append(extra, EvalNode{ID: det.ID, Role: det.Role, BBox: det.BBox, BestID: bestID, BestBBox: bestBBox, BestIoU: bestScore, PassID: det.Source.PassID, Label: det.RawLabel})
	}
	missed := []EvalNode{}
	for i, gold := range golds {
		if usedGold[i] {
			continue
		}
		bestID, bestBBox, bestScore := bestCandidate(gold, dets)
		missed = append(missed, EvalNode{ID: gold.ID, Role: gold.Role, BBox: gold.BBox, BestID: bestID, BestBBox: bestBBox, BestIoU: bestScore})
	}
	return matched, extra, missed
}

func bestGolden(det Candidate, golds []goldenNode) (string, BBox, float64) {
	bestID := ""
	bestBBox := BBox{}
	bestScore := 0.0
	for _, gold := range golds {
		score := iou(det.BBox, gold.BBox)
		if score > bestScore {
			bestScore = score
			bestID = gold.ID
			bestBBox = gold.BBox
		}
	}
	return bestID, bestBBox, bestScore
}

func bestCandidate(gold goldenNode, dets []Candidate) (string, BBox, float64) {
	bestID := ""
	bestBBox := BBox{}
	bestScore := 0.0
	for _, det := range dets {
		score := iou(gold.BBox, det.BBox)
		if score > bestScore {
			bestScore = score
			bestID = det.ID
			bestBBox = det.BBox
		}
	}
	return bestID, bestBBox, bestScore
}

func sortedEvalRoles(candidates []Candidate, golden []goldenNode) []Role {
	seen := map[Role]bool{}
	for _, item := range candidates {
		seen[item.Role] = true
	}
	for _, item := range golden {
		seen[item.Role] = true
	}
	roles := make([]Role, 0, len(seen))
	for role := range seen {
		roles = append(roles, role)
	}
	sort.SliceStable(roles, func(i, j int) bool { return roles[i] < roles[j] })
	return roles
}

func filterCandidatesByRole(items []Candidate, role Role) []Candidate {
	out := []Candidate{}
	for _, item := range items {
		if item.Role == role {
			out = append(out, item)
		}
	}
	return out
}

func filterGoldenByRole(items []goldenNode, role Role) []goldenNode {
	out := []goldenNode{}
	for _, item := range items {
		if item.Role == role {
			out = append(out, item)
		}
	}
	return out
}

func ratio(num, den int) float64 {
	if den == 0 {
		return 0
	}
	return float64(num) / float64(den)
}

func f1(precision, recall float64) float64 {
	if precision+recall == 0 {
		return 0
	}
	return 2 * precision * recall / (precision + recall)
}

func matchedRoleCount(items []RoleEval) int {
	count := 0
	for _, item := range items {
		if item.MatchedAt05 > 0 {
			count++
		}
	}
	return count
}

func sortEvalNodes(items []EvalNode) {
	sort.SliceStable(items, func(i, j int) bool {
		if items[i].Role != items[j].Role {
			return items[i].Role < items[j].Role
		}
		if items[i].BestIoU != items[j].BestIoU {
			return items[i].BestIoU < items[j].BestIoU
		}
		return items[i].ID < items[j].ID
	})
}
