package canvas

import (
	"fmt"
	"reflect"
	"sort"
	"strings"
)

const ExpectTencentComic018 = "tencent-comic-018"

func CheckExpectation(analysis Analysis, expectation string) []ExpectationFailure {
	switch expectation {
	case "", "none":
		return nil
	case ExpectTencentComic018:
		return checkTencentComic018(analysis)
	default:
		return []ExpectationFailure{{
			Check:    "expectation",
			Expected: "known expectation",
			Actual:   expectation,
		}}
	}
}

func checkTencentComic018(a Analysis) []ExpectationFailure {
	var failures []ExpectationFailure
	add := func(check string, expected string, actual string) {
		if expected != actual {
			failures = append(failures, ExpectationFailure{Check: check, Expected: expected, Actual: actual})
		}
	}
	addInt := func(check string, expected int, actual int) {
		if expected != actual {
			failures = append(failures, ExpectationFailure{Check: check, Expected: fmt.Sprintf("%d", expected), Actual: fmt.Sprintf("%d", actual)})
		}
	}
	addMap := func(check string, expected map[string]int, actual map[string]int) {
		if !reflect.DeepEqual(expected, actual) {
			failures = append(failures, ExpectationFailure{Check: check, Expected: formatCounts(expected), Actual: formatCounts(actual)})
		}
	}

	add("rootName", "Root", a.RootName)
	addInt("rootWidth", 665, a.RootBBox.Width)
	addInt("rootHeight", 1440, a.RootBBox.Height)
	addInt("rootChildCount", 3, a.RootChildCount)
	addInt("nodeCount", 146, a.NodeCount)
	addInt("maxDepth", 6, a.MaxDepth)
	addMap("typeCounts", map[string]int{
		"FRAME":             41,
		"TEXT":              48,
		"ROUNDED_RECTANGLE": 57,
	}, a.TypeCounts)
	addMap("roleCounts", map[string]int{
		"TextView":         48,
		"ImageView":        39,
		"ViewGroup":        24,
		"Button":           9,
		"bg_Button":        9,
		"Background":       9,
		"ListView":         5,
		"ActionBar":        1,
		"BottomNavigation": 1,
		"root":             1,
	}, a.RoleCounts)
	addInt("schemaCoveragePresent", 146, a.SchemaCoverage.Present)
	addInt("schemaCoverageTotal", 146, a.SchemaCoverage.Total)
	addInt("guidCoveragePresent", 146, a.GUIDCoverage.Present)
	addInt("guidCoverageTotal", 146, a.GUIDCoverage.Total)
	addInt("suffixPresent", 146, a.Suffix.Present)
	addInt("suffixMin", 0, a.Suffix.Min)
	addInt("suffixMax", 145, a.Suffix.Max)
	addInt("suffixMissing", 0, len(a.Suffix.Missing))
	addInt("suffixDuplicates", 0, len(a.Suffix.Duplicates))
	addInt("multiChildParents", 41, a.ChildOrder.MultiChildParents)
	addInt("strictDescendingParents", 41, a.ChildOrder.StrictDescendingParents)
	addLastChild := func(role string, total int, last int) {
		report := a.LastChild[role]
		addInt(role+"Total", total, report.Total)
		addInt(role+"Last", last, report.Last)
	}
	addLastChild("Background", 9, 9)
	addLastChild("bg_Button", 9, 9)
	addInt("buttonModeTextImageBg", 2, a.ButtonModes["TextView+ImageView+bg_Button"])
	addInt("buttonModeTextBg", 7, a.ButtonModes["TextView+bg_Button"])
	addInt("textViewCount", 48, a.Text.TextViewCount)
	addInt("textNameCharacterMatch", 48, a.Text.NameCharacterMatch)
	addInt("imageFillCount", 48, a.ImageFills.ImageFillCount)
	addInt("uniqueImageHashCount", 48, a.ImageFills.UniqueHashCount)
	addInt("cornerRadiusNodeCount", 8, a.CornerRadius.NodeCount)
	addMap("cornerRadiusByRole", map[string]int{
		"Background": 4,
		"bg_Button":  4,
	}, a.CornerRadius.ByRole)
	addInt("roleMappingViolations", 0, len(a.RoleMappingViolations))
	return failures
}

func formatCounts(counts map[string]int) string {
	keys := make([]string, 0, len(counts))
	for key := range counts {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	parts := make([]string, 0, len(keys))
	for _, key := range keys {
		parts = append(parts, fmt.Sprintf("%s=%d", key, counts[key]))
	}
	return strings.Join(parts, ",")
}
