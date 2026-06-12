package ocr

import (
	"encoding/json"
	"fmt"
	"os"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/contract"
)

type Document struct {
	Image    ImageInfo      `json:"image"`
	Provider string         `json:"provider,omitempty"`
	Model    string         `json:"model,omitempty"`
	Status   string         `json:"status,omitempty"`
	Blocks   []Block        `json:"blocks"`
	Warnings []Warning      `json:"warnings,omitempty"`
	Meta     map[string]any `json:"meta,omitempty"`
	Error    *Error         `json:"error,omitempty"`
}

type ImageInfo struct {
	Width  int `json:"width"`
	Height int `json:"height"`
}

type Block struct {
	ID         string         `json:"id"`
	Text       string         `json:"text"`
	BBox       contract.BBox  `json:"bbox"`
	Confidence float64        `json:"confidence,omitempty"`
	Source     string         `json:"source,omitempty"`
	Meta       map[string]any `json:"meta,omitempty"`
}

type Warning struct {
	Code    string `json:"code"`
	Message string `json:"message"`
	BlockID string `json:"blockId,omitempty"`
}

type Error struct {
	Code    string `json:"code"`
	Message string `json:"message"`
}

func Read(path string) (Document, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return Document{}, err
	}
	doc, err := parseDocument(data)
	if err != nil {
		return Document{}, err
	}
	for i, block := range doc.Blocks {
		if block.ID == "" {
			return Document{}, fmt.Errorf("ocr block %d is missing id", i)
		}
		if block.BBox.Width <= 0 || block.BBox.Height <= 0 {
			return Document{}, fmt.Errorf("ocr block %s has invalid bbox", block.ID)
		}
	}
	return doc, nil
}

func parseDocument(data []byte) (Document, error) {
	var raw struct {
		Image     ImageInfo      `json:"image"`
		ImageSize ImageInfo      `json:"imageSize"`
		Provider  string         `json:"provider,omitempty"`
		Model     string         `json:"model,omitempty"`
		Status    string         `json:"status,omitempty"`
		Blocks    []rawBlock     `json:"blocks"`
		Warnings  []Warning      `json:"warnings,omitempty"`
		Meta      map[string]any `json:"meta,omitempty"`
		Error     *Error         `json:"error,omitempty"`
	}
	if err := json.Unmarshal(data, &raw); err != nil {
		return Document{}, err
	}
	image := raw.Image
	if image.Width == 0 && image.Height == 0 {
		image = raw.ImageSize
	}
	blocks := make([]Block, 0, len(raw.Blocks))
	for i, item := range raw.Blocks {
		bbox, err := parseBBox(item.BBox)
		if err != nil {
			return Document{}, fmt.Errorf("ocr block %d invalid bbox: %w", i, err)
		}
		blocks = append(blocks, Block{
			ID:         item.ID,
			Text:       item.Text,
			BBox:       bbox,
			Confidence: item.Confidence,
			Source:     item.Source,
			Meta:       item.Meta,
		})
	}
	return Document{
		Image:    image,
		Provider: raw.Provider,
		Model:    raw.Model,
		Status:   raw.Status,
		Blocks:   blocks,
		Warnings: raw.Warnings,
		Meta:     raw.Meta,
		Error:    raw.Error,
	}, nil
}

type rawBlock struct {
	ID         string          `json:"id"`
	Text       string          `json:"text"`
	BBox       json.RawMessage `json:"bbox"`
	Confidence float64         `json:"confidence,omitempty"`
	Source     string          `json:"source,omitempty"`
	Meta       map[string]any  `json:"meta,omitempty"`
}

func parseBBox(data json.RawMessage) (contract.BBox, error) {
	var object contract.BBox
	if err := json.Unmarshal(data, &object); err == nil && object.Width > 0 && object.Height > 0 {
		return object, nil
	}
	var list []int
	if err := json.Unmarshal(data, &list); err != nil {
		return contract.BBox{}, err
	}
	if len(list) != 4 {
		return contract.BBox{}, fmt.Errorf("expected 4 numbers")
	}
	return contract.BBox{X: list[0], Y: list[1], Width: list[2], Height: list[3]}, nil
}

func Write(path string, doc Document) error {
	data, err := json.MarshalIndent(doc, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, data, 0o644)
}
