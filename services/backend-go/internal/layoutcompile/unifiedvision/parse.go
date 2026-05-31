package unifiedvision

import (
	"encoding/json"
	"fmt"
	"strings"
)

func parseModelResult(text string) (ModelResult, error) {
	cleaned := stripJSONFence(text)
	var result ModelResult
	if err := json.Unmarshal([]byte(cleaned), &result); err != nil {
		return ModelResult{}, fmt.Errorf("parse unified vision result: %w", err)
	}
	if strings.TrimSpace(result.Version) == "" {
		result.Version = ResultVersion
	}
	return result, nil
}

func stripJSONFence(text string) string {
	text = strings.TrimSpace(text)
	if !strings.HasPrefix(text, "```") {
		return text
	}
	lines := strings.Split(text, "\n")
	out := make([]string, 0, len(lines))
	for _, line := range lines {
		if strings.HasPrefix(strings.TrimSpace(line), "```") {
			continue
		}
		out = append(out, line)
	}
	return strings.TrimSpace(strings.Join(out, "\n"))
}
