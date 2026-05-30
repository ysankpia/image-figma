package control

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/ir"
)

func TestSynthesizeCreatesButtonWithBackgroundLastChild(t *testing.T) {
	doc := leafDoc([]ir.Node{
		{
			ID:          "bg",
			Role:        ir.RoleBackground,
			SourceBBox:  ir.BBox{X: 10, Y: 10, Width: 120, Height: 40},
			FigmaBBox:   ir.BBox{X: 10, Y: 10, Width: 120, Height: 40},
			FigmaType:   ir.FigmaRoundedRectangle,
			VisibleName: "Background",
			Evidence:    []ir.Evidence{{Kind: "solid_background"}},
		},
		{
			ID:          "text",
			Role:        ir.RoleTextView,
			SourceBBox:  ir.BBox{X: 35, Y: 20, Width: 60, Height: 18},
			FigmaBBox:   ir.BBox{X: 35, Y: 20, Width: 60, Height: 18},
			FigmaType:   ir.FigmaText,
			VisibleName: "Pay",
			Text:        &ir.Text{Characters: "Pay"},
		},
	})
	result, err := Synthesize(doc)
	if err != nil {
		t.Fatalf("Synthesize() error = %v", err)
	}
	if result.Diagnostics.ControlCount != 1 || len(result.Controls) != 1 || len(result.Remaining) != 0 {
		t.Fatalf("unexpected stage result: %#v", result.Diagnostics)
	}
	out := ToDocument(result)
	if out.Summary.RoleCounts[string(ir.RoleButton)] != 1 || out.Summary.RoleCounts[string(ir.RoleBgButton)] != 1 {
		t.Fatalf("expected button roles, got %#v", out.Summary.RoleCounts)
	}
	button := out.Root.Children[0]
	if button.Role != ir.RoleButton || button.VisibleName != "Button" || len(button.Children) != 2 {
		t.Fatalf("unexpected button node: %#v", button)
	}
	last := button.Children[len(button.Children)-1]
	if last.Role != ir.RoleBgButton || last.VisibleName != "Background" {
		t.Fatalf("expected bg_Button last child, got %#v", button.Children)
	}
	if out.Summary.NodeCount != 4 || len(out.Root.Children) != 1 {
		t.Fatalf("expected foreground/background removed from root, summary=%#v root=%#v", out.Summary, out.Root.Children)
	}
}

func TestSynthesizeAllowsTightTextInsidePixelSurface(t *testing.T) {
	doc := leafDoc([]ir.Node{
		{
			ID:          "bg",
			Role:        ir.RoleBackground,
			SourceBBox:  ir.BBox{X: 249, Y: 14, Width: 167, Height: 42},
			FigmaBBox:   ir.BBox{X: 249, Y: 14, Width: 167, Height: 42},
			FigmaType:   ir.FigmaRoundedRectangle,
			VisibleName: "Background",
			Evidence:    []ir.Evidence{{Kind: "solid_background", Notes: "surface_region_token"}},
		},
		{
			ID:          "text",
			Role:        ir.RoleTextView,
			SourceBBox:  ir.BBox{X: 251, Y: 15, Width: 162, Height: 36},
			FigmaBBox:   ir.BBox{X: 251, Y: 15, Width: 162, Height: 36},
			FigmaType:   ir.FigmaText,
			VisibleName: "uinotes.com",
			Text:        &ir.Text{Characters: "uinotes.com"},
		},
	})
	result, err := Synthesize(doc)
	if err != nil {
		t.Fatalf("Synthesize() error = %v", err)
	}
	out := ToDocument(result)
	if out.Summary.RoleCounts[string(ir.RoleButton)] != 1 {
		t.Fatalf("expected tight text surface to synthesize a button, got %#v", out.Summary.RoleCounts)
	}
}

func TestSynthesizeCreatesEditTextFromWideIconOnlyBackground(t *testing.T) {
	doc := leafDoc([]ir.Node{
		{
			ID:          "bg",
			Role:        ir.RoleBackground,
			SourceBBox:  ir.BBox{X: 10, Y: 10, Width: 180, Height: 48},
			FigmaBBox:   ir.BBox{X: 10, Y: 10, Width: 180, Height: 48},
			FigmaType:   ir.FigmaRoundedRectangle,
			VisibleName: "Background",
			Evidence:    []ir.Evidence{{Kind: "rounded_background"}},
		},
		{
			ID:          "icon",
			Role:        ir.RoleImageView,
			SourceBBox:  ir.BBox{X: 24, Y: 22, Width: 18, Height: 18},
			FigmaBBox:   ir.BBox{X: 24, Y: 22, Width: 18, Height: 18},
			FigmaType:   ir.FigmaRoundedRectangle,
			VisibleName: "Image",
			Asset:       &ir.Asset{Kind: "crop"},
		},
	})
	result, err := Synthesize(doc)
	if err != nil {
		t.Fatalf("Synthesize() error = %v", err)
	}
	out := ToDocument(result)
	edit := out.Root.Children[0]
	if edit.Role != ir.RoleEditText || edit.VisibleName != "Text" {
		t.Fatalf("expected EditText, got %#v", edit)
	}
	if edit.Children[len(edit.Children)-1].Role != ir.RoleBgEditText {
		t.Fatalf("expected bg_EditText last child, got %#v", edit.Children)
	}
}

func TestSynthesizeConsumesControlEdgeImageFragments(t *testing.T) {
	doc := leafDoc([]ir.Node{
		{
			ID:          "bg",
			Role:        ir.RoleBackground,
			SourceBBox:  ir.BBox{X: 250, Y: 15, Width: 166, Height: 40},
			FigmaBBox:   ir.BBox{X: 250, Y: 15, Width: 166, Height: 40},
			FigmaType:   ir.FigmaRoundedRectangle,
			VisibleName: "Background",
			Evidence:    []ir.Evidence{{Kind: "control_surface_background"}},
		},
		{
			ID:          "left_edge",
			Role:        ir.RoleImageView,
			SourceBBox:  ir.BBox{X: 250, Y: 15, Width: 17, Height: 40},
			FigmaBBox:   ir.BBox{X: 250, Y: 15, Width: 17, Height: 40},
			FigmaType:   ir.FigmaRoundedRectangle,
			VisibleName: "Image",
			Asset:       &ir.Asset{Kind: "crop"},
		},
		{
			ID:          "right_edge",
			Role:        ir.RoleImageView,
			SourceBBox:  ir.BBox{X: 398, Y: 15, Width: 18, Height: 40},
			FigmaBBox:   ir.BBox{X: 398, Y: 15, Width: 18, Height: 40},
			FigmaType:   ir.FigmaRoundedRectangle,
			VisibleName: "Image",
			Asset:       &ir.Asset{Kind: "crop"},
		},
		{
			ID:          "text",
			Role:        ir.RoleTextView,
			SourceBBox:  ir.BBox{X: 258, Y: 24, Width: 149, Height: 21},
			FigmaBBox:   ir.BBox{X: 258, Y: 24, Width: 149, Height: 21},
			FigmaType:   ir.FigmaText,
			VisibleName: "uinotes.com",
			Text:        &ir.Text{Characters: "uinotes.com"},
		},
	})
	result, err := Synthesize(doc)
	if err != nil {
		t.Fatalf("Synthesize() error = %v", err)
	}
	if len(result.Controls) != 1 || len(result.Remaining) != 0 {
		t.Fatalf("expected accepted control with edge fragments consumed, controls=%#v remaining=%#v", result.Controls, result.Remaining)
	}
	button := result.Controls[0]
	if button.Role != ir.RoleButton || len(button.Children) != 2 {
		t.Fatalf("expected text plus bg_Button only, got %#v", button)
	}
	if button.Children[0].ID != "text" || button.Children[1].Role != ir.RoleBgButton {
		t.Fatalf("unexpected button children: %#v", button.Children)
	}
}

func TestSynthesizeKeepsRealInlineButtonIcon(t *testing.T) {
	doc := leafDoc([]ir.Node{
		{
			ID:          "bg",
			Role:        ir.RoleBackground,
			SourceBBox:  ir.BBox{X: 244, Y: 10, Width: 166, Height: 41},
			FigmaBBox:   ir.BBox{X: 244, Y: 10, Width: 166, Height: 41},
			FigmaType:   ir.FigmaRoundedRectangle,
			VisibleName: "Background",
			Evidence:    []ir.Evidence{{Kind: "control_surface_background"}},
		},
		{
			ID:          "icon",
			Role:        ir.RoleImageView,
			SourceBBox:  ir.BBox{X: 257, Y: 22, Width: 23, Height: 22},
			FigmaBBox:   ir.BBox{X: 257, Y: 22, Width: 23, Height: 22},
			FigmaType:   ir.FigmaRoundedRectangle,
			VisibleName: "Image",
			Asset:       &ir.Asset{Kind: "crop"},
		},
		{
			ID:          "text",
			Role:        ir.RoleTextView,
			SourceBBox:  ir.BBox{X: 283, Y: 24, Width: 120, Height: 20},
			FigmaBBox:   ir.BBox{X: 283, Y: 24, Width: 120, Height: 20},
			FigmaType:   ir.FigmaText,
			VisibleName: "uinotes.com",
			Text:        &ir.Text{Characters: "uinotes.com"},
		},
	})
	result, err := Synthesize(doc)
	if err != nil {
		t.Fatalf("Synthesize() error = %v", err)
	}
	if len(result.Controls) != 1 {
		t.Fatalf("expected one button, got %#v", result.Controls)
	}
	button := result.Controls[0]
	if len(button.Children) != 3 {
		t.Fatalf("expected icon, text, and bg_Button, got %#v", button.Children)
	}
	if button.Children[0].ID != "icon" || button.Children[1].ID != "text" || button.Children[2].Role != ir.RoleBgButton {
		t.Fatalf("unexpected button children: %#v", button.Children)
	}
}

func TestSynthesizeRejectsContentPanelLikeButton(t *testing.T) {
	doc := leafDoc([]ir.Node{
		{
			ID:          "panel_bg",
			Role:        ir.RoleBackground,
			SourceBBox:  ir.BBox{X: 10, Y: 10, Width: 122, Height: 73},
			FigmaBBox:   ir.BBox{X: 10, Y: 10, Width: 122, Height: 73},
			FigmaType:   ir.FigmaRoundedRectangle,
			VisibleName: "Background",
			Evidence:    []ir.Evidence{{Kind: "control_surface_background"}},
		},
		{
			ID:          "panel_text",
			Role:        ir.RoleTextView,
			SourceBBox:  ir.BBox{X: 35, Y: 54, Width: 68, Height: 22},
			FigmaBBox:   ir.BBox{X: 35, Y: 54, Width: 68, Height: 22},
			FigmaType:   ir.FigmaText,
			VisibleName: "Reward",
			Text:        &ir.Text{Characters: "Reward"},
		},
	})
	result, err := Synthesize(doc)
	if err != nil {
		t.Fatalf("Synthesize() error = %v", err)
	}
	if len(result.Controls) != 0 {
		t.Fatalf("expected content panel to be rejected, got controls %#v", result.Controls)
	}
	if len(result.Rejections) == 0 || result.Rejections[0].Reason != "foreground_content_panel_like" {
		t.Fatalf("expected content-panel rejection, got %#v", result.Rejections)
	}
	if len(result.Remaining) != 2 {
		t.Fatalf("expected background and text to remain, got %#v", result.Remaining)
	}
}

func TestSynthesizeRejectsTextOnlyNearFillSurface(t *testing.T) {
	doc := leafDoc([]ir.Node{
		{
			ID:          "label_bg",
			Role:        ir.RoleBackground,
			SourceBBox:  ir.BBox{X: 20, Y: 30, Width: 88, Height: 40},
			FigmaBBox:   ir.BBox{X: 20, Y: 30, Width: 88, Height: 40},
			FigmaType:   ir.FigmaRoundedRectangle,
			VisibleName: "Background",
			Evidence:    []ir.Evidence{{Kind: "control_surface_background"}},
		},
		{
			ID:          "label_text",
			Role:        ir.RoleTextView,
			SourceBBox:  ir.BBox{X: 20, Y: 31, Width: 86, Height: 36},
			FigmaBBox:   ir.BBox{X: 20, Y: 31, Width: 86, Height: 36},
			FigmaType:   ir.FigmaText,
			VisibleName: "Label",
			Text:        &ir.Text{Characters: "Label"},
		},
	})
	result, err := Synthesize(doc)
	if err != nil {
		t.Fatalf("Synthesize() error = %v", err)
	}
	if len(result.Controls) != 0 {
		t.Fatalf("expected near-fill text surface to be rejected, got controls %#v", result.Controls)
	}
	if len(result.Rejections) == 0 || result.Rejections[0].Reason != "foreground_text_near_fill_surface" {
		t.Fatalf("expected near-fill rejection, got %#v", result.Rejections)
	}
}

func TestSynthesizeKeepsIconOverTextButton(t *testing.T) {
	doc := leafDoc([]ir.Node{
		{
			ID:          "button_bg",
			Role:        ir.RoleBackground,
			SourceBBox:  ir.BBox{X: 10, Y: 10, Width: 58, Height: 58},
			FigmaBBox:   ir.BBox{X: 10, Y: 10, Width: 58, Height: 58},
			FigmaType:   ir.FigmaRoundedRectangle,
			VisibleName: "Background",
			Evidence:    []ir.Evidence{{Kind: "control_surface_background"}},
		},
		{
			ID:          "button_icon",
			Role:        ir.RoleImageView,
			SourceBBox:  ir.BBox{X: 24, Y: 14, Width: 30, Height: 28},
			FigmaBBox:   ir.BBox{X: 24, Y: 14, Width: 30, Height: 28},
			FigmaType:   ir.FigmaRoundedRectangle,
			VisibleName: "Image",
			Asset:       &ir.Asset{Kind: "crop"},
		},
		{
			ID:          "button_text",
			Role:        ir.RoleTextView,
			SourceBBox:  ir.BBox{X: 20, Y: 44, Width: 40, Height: 22},
			FigmaBBox:   ir.BBox{X: 20, Y: 44, Width: 40, Height: 22},
			FigmaType:   ir.FigmaText,
			VisibleName: "Game",
			Text:        &ir.Text{Characters: "Game"},
		},
	})
	result, err := Synthesize(doc)
	if err != nil {
		t.Fatalf("Synthesize() error = %v", err)
	}
	if len(result.Controls) != 1 || result.Controls[0].Role != ir.RoleButton {
		t.Fatalf("expected icon-over-text button, got %#v", result.Controls)
	}
}

func TestCompileReadsIRAndWritesArtifacts(t *testing.T) {
	tmp := t.TempDir()
	input := filepath.Join(tmp, "codia_leaf_ir.v1.json")
	doc := leafDoc(nil)
	data := []byte(`{"schemaName":"CodiaIR","version":"1.0","source":{},"root":{"id":"root_0","role":"root","source_bbox":{"x":0,"y":0,"width":100,"height":100},"figma_bbox":{"x":0,"y":0,"width":100,"height":100},"figma_type":"FRAME","visible_name":"Root"},"summary":{"nodeCount":1,"maxDepth":0,"roleCounts":{"root":1},"figmaTypeCounts":{"FRAME":1}}}`)
	if doc.SchemaName == "" {
		t.Fatal("unreachable")
	}
	if err := os.WriteFile(input, data, 0o644); err != nil {
		t.Fatalf("write input: %v", err)
	}
	out, err := Compile(Options{InputPath: input})
	if err != nil {
		t.Fatalf("Compile() error = %v", err)
	}
	if err := WriteArtifacts(tmp, out); err != nil {
		t.Fatalf("WriteArtifacts() error = %v", err)
	}
	for _, name := range []string{ArtifactName, StageArtifactName, "codia_control_ir_report.md"} {
		if _, err := os.Stat(filepath.Join(tmp, name)); err != nil {
			t.Fatalf("expected artifact %s: %v", name, err)
		}
	}
}

func leafDoc(children []ir.Node) ir.Document {
	root := ir.Node{
		ID:          "root_0",
		Role:        ir.RoleRoot,
		SourceBBox:  ir.BBox{X: 0, Y: 0, Width: 320, Height: 640},
		FigmaBBox:   ir.BBox{X: 0, Y: 0, Width: 320, Height: 640},
		FigmaType:   ir.FigmaFrame,
		VisibleName: "Root",
		Children:    children,
	}
	return ir.Document{
		SchemaName: ir.SchemaName,
		Version:    ir.Version,
		Root:       root,
		Summary: ir.Summary{
			NodeCount:       len(children) + 1,
			RoleCounts:      map[string]int{"root": 1},
			FigmaTypeCounts: map[string]int{"FRAME": 1},
		},
	}
}
