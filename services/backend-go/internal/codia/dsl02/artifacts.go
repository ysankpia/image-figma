package dsl02

import (
	"encoding/json"
	"os"
	"path/filepath"
)

const ArtifactName = "codia_runtime.dsl.v0_2.json"

func WriteArtifact(outputDir string, doc Document) error {
	if err := os.MkdirAll(outputDir, 0o755); err != nil {
		return err
	}
	data, err := json.MarshalIndent(doc, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(filepath.Join(outputDir, ArtifactName), data, 0o644)
}
