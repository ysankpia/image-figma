package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"

	"github.com/luqing-studio/image-figma/services/pencil-go/internal/pencil"
	"github.com/luqing-studio/image-figma/services/pencil-go/internal/project"
)

type inputsFlag []string

func (f *inputsFlag) String() string {
	return fmt.Sprint([]string(*f))
}

func (f *inputsFlag) Set(value string) error {
	*f = append(*f, value)
	return nil
}

func main() {
	var inputs inputsFlag
	flag.Var(&inputs, "input", "PNG file, PNG directory, or manifest JSON. Repeatable.")
	out := flag.String("out", "", "Output project directory.")
	projectName := flag.String("project-name", "M29 Pencil Project", "Project name.")
	mode := flag.String("mode", string(pencil.ModeAll), "Export mode: clean-editable, visual-fidelity, visual-ocr, all.")
	columns := flag.String("columns", "auto", "Grid columns: auto or integer.")
	includeDebug := flag.Bool("include-debug", true, "Include debug evidence and report.")
	ocrProvider := flag.String("ocr-provider", os.Getenv("OCR_PROVIDER"), "OCR provider: baidu_ppocrv5, fake, none.")
	flag.Parse()

	if len(inputs) == 0 || *out == "" {
		flag.Usage()
		os.Exit(2)
	}
	result, err := project.Export(project.Options{
		Inputs:       []string(inputs),
		OutputDir:    *out,
		ProjectName:  *projectName,
		Mode:         pencil.Mode(*mode),
		Columns:      *columns,
		IncludeDebug: *includeDebug,
		OCRProvider:  *ocrProvider,
	})
	if err != nil {
		fmt.Fprintf(os.Stderr, "pencilexport: %v\n", err)
		os.Exit(1)
	}
	payload := map[string]any{
		"outDir":    result.OutputDir,
		"zipPath":   result.ZipPath,
		"pageCount": result.Manifest.PageCount,
		"modes":     result.Manifest.Modes,
	}
	data, _ := json.MarshalIndent(payload, "", "  ")
	fmt.Println(string(data))
}
