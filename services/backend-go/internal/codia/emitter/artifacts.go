package emitter

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
)

func WriteArtifact(outputDir string, doc Document) error {
	if outputDir == "" {
		return fmt.Errorf("missing output dir")
	}
	if err := os.MkdirAll(outputDir, 0o755); err != nil {
		return err
	}
	data, err := json.MarshalIndent(doc, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(filepath.Join(outputDir, "codia_figma_like_tree.v1.json"), data, 0o644)
}
