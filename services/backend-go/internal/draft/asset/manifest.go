package asset

import (
	"encoding/json"
	"os"
	"path/filepath"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/draft/contract"
)

const ManifestName = "asset_manifest.json"

type Manifest struct {
	Version string           `json:"version"`
	Assets  []contract.Asset `json:"assets"`
}

func FromGraph(doc contract.Document) Manifest {
	return Manifest{
		Version: "draft_asset_manifest.v1",
		Assets:  append([]contract.Asset(nil), doc.Assets...),
	}
}

func WriteManifest(dir string, manifest Manifest) error {
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return err
	}
	data, err := json.MarshalIndent(manifest, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(filepath.Join(dir, ManifestName), append(data, '\n'), 0o644)
}
