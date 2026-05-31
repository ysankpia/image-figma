package unifiedvision

import (
	"encoding/json"
	"fmt"
	"strings"
)

func buildPrompt(batch BatchInput, repair *BatchValidation) string {
	var b strings.Builder
	fmt.Fprintf(&b, "You are a UI layout relationship analyzer.\n\n")
	fmt.Fprintf(&b, "You receive a cropped section of a UI screenshot and a list of detected elements with precise bounding boxes.\n")
	fmt.Fprintf(&b, "The image is the cropBBox region. bbox is global source-image coordinates. bboxLocal is crop-local coordinates.\n\n")
	fmt.Fprintf(&b, "Batch: %s\n", batch.ID)
	fmt.Fprintf(&b, "Section: %s\n", batch.SectionID)
	fmt.Fprintf(&b, "Section bbox: %s\n", jsonRect(batch.SectionBBox))
	fmt.Fprintf(&b, "Crop bbox: %s\n", jsonRect(batch.CropBBox))
	fmt.Fprintf(&b, "Complexity: itemCount=%d yBandCount=%d score=%.2f\n\n", batch.Complexity.ItemCount, batch.Complexity.YBandCount, batch.Complexity.Score)
	fmt.Fprintf(&b, "Task:\n")
	fmt.Fprintf(&b, "1. Group elements that visually belong together in this crop.\n")
	fmt.Fprintf(&b, "2. Use only flat groups in v1. Do not nest groups.\n")
	fmt.Fprintf(&b, "3. For each group, choose direction horizontal or vertical and estimate gap in pixels.\n")
	fmt.Fprintf(&b, "4. For text elements only, optionally estimate fontSize, fontWeight, and color.\n\n")
	fmt.Fprintf(&b, "Hard rules:\n")
	fmt.Fprintf(&b, "- Output only valid JSON. No markdown fences and no prose.\n")
	fmt.Fprintf(&b, "- Reference elements only by IDs in Detected elements.\n")
	fmt.Fprintf(&b, "- Do not put an ID in more than one group.\n")
	fmt.Fprintf(&b, "- Do not create single-member groups.\n")
	fmt.Fprintf(&b, "- Do not output or modify OCR text, bboxes, image assets, HTML, CSS, or Figma nodes.\n")
	fmt.Fprintf(&b, "- Prefer small credible groups. If uncertain, leave elements ungrouped.\n")
	fmt.Fprintf(&b, "- Use confidence from 0.0 to 1.0. Use confidence below 0.70 for weak guesses.\n\n")
	if repair != nil && repair.RejectedCount > 0 {
		fmt.Fprintf(&b, "Repair context:\n")
		fmt.Fprintf(&b, "The previous response had rejected groups. Return a corrected full result for this same batch.\n")
		fmt.Fprintf(&b, "Rejected reasons from validator:\n")
		for _, reason := range repairReasons(*repair) {
			fmt.Fprintf(&b, "- %s\n", reason)
		}
		fmt.Fprintf(&b, "\n")
	}
	fmt.Fprintf(&b, "Detected elements (%d):\n%s\n\n", len(batch.Evidence), promptEvidenceJSON(batch))
	fmt.Fprintf(&b, "Return JSON exactly shaped like:\n")
	fmt.Fprintf(&b, `{"version":"unified_vision_result.v1","groups":[{"id":"group_1","name":"short_name","direction":"horizontal","gap":12,"members":["id1","id2"],"confidence":0.8,"reason":"short reason"}],"elementStyles":{"id1":{"fontSize":16,"fontWeight":600,"color":"#111111"}},"ungrouped":["id3"],"warnings":[]}`)
	return b.String()
}

func jsonRect(value any) string {
	data, _ := json.Marshal(value)
	return string(data)
}

func repairReasons(batch BatchValidation) []string {
	if batch.Reason == "" {
		return []string{"validation rejected one or more groups"}
	}
	return []string{batch.Reason}
}
