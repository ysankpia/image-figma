package visualtree

import (
	"bufio"
	"encoding/json"
	"fmt"
	"os"
	"sort"
	"strings"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/contract"
)

const traceStage = "visualtree"

type TraceEvent struct {
	EventID        string         `json:"eventId"`
	Stage          string         `json:"stage"`
	Operation      string         `json:"operation"`
	ParentNodeID   string         `json:"parentNodeId,omitempty"`
	SpatialDepth   int            `json:"spatialDepth,omitempty"`
	InputNodeIDs   []string       `json:"inputNodeIds,omitempty"`
	OutputNodeIDs  []string       `json:"outputNodeIds,omitempty"`
	InputBBox      *contract.BBox `json:"inputBBox,omitempty"`
	Decision       string         `json:"decision"`
	DecisionClass  string         `json:"decisionClass,omitempty"`
	GroupKind      string         `json:"groupKind,omitempty"`
	Reason         string         `json:"reason,omitempty"`
	Metrics        map[string]any `json:"metrics"`
	Thresholds     map[string]any `json:"thresholds"`
	SourceEvidence map[string]any `json:"sourceEvidence"`
}

type TraceRecorder struct {
	events []TraceEvent
	nextID int
}

func NewTraceRecorder() *TraceRecorder {
	return &TraceRecorder{nextID: 1}
}

func (r *TraceRecorder) Record(event TraceEvent) {
	if r == nil {
		return
	}
	event.EventID = fmt.Sprintf("evt_%06d", r.nextID)
	r.nextID++
	if event.Stage == "" {
		event.Stage = traceStage
	}
	if event.Metrics == nil {
		event.Metrics = map[string]any{}
	}
	if event.Thresholds == nil {
		event.Thresholds = map[string]any{}
	}
	if event.SourceEvidence == nil {
		event.SourceEvidence = map[string]any{}
	}
	r.events = append(r.events, event)
}

func (r *TraceRecorder) Events() []TraceEvent {
	if r == nil {
		return nil
	}
	out := make([]TraceEvent, len(r.events))
	copy(out, r.events)
	return out
}

func writeTraceJSONL(path string, events []TraceEvent) error {
	file, err := os.Create(path)
	if err != nil {
		return err
	}
	defer file.Close()
	writer := bufio.NewWriter(file)
	for _, event := range events {
		data, err := json.Marshal(event)
		if err != nil {
			return err
		}
		if _, err := writer.Write(data); err != nil {
			return err
		}
		if err := writer.WriteByte('\n'); err != nil {
			return err
		}
	}
	return writer.Flush()
}

func writeTraceReport(path string, root Node, events []TraceEvent) error {
	var b strings.Builder
	fmt.Fprintf(&b, "# M29 Visual Tree Decision Trace Report\n\n")
	fmt.Fprintf(&b, "- events: %d\n", len(events))
	fmt.Fprintf(&b, "- operations: %s\n", formatTraceCounts(countTrace(events, func(event TraceEvent) string { return event.Operation })))
	fmt.Fprintf(&b, "- decisions: %s\n", formatTraceCounts(countTrace(events, func(event TraceEvent) string { return event.Decision })))
	fmt.Fprintf(&b, "- decisionClasses: %s\n", formatTraceCounts(countTrace(events, func(event TraceEvent) string { return event.DecisionClass })))
	fmt.Fprintf(&b, "- groupKinds: %s\n\n", formatTraceCounts(countTrace(events, func(event TraceEvent) string { return event.GroupKind })))

	orphanIDs := orphanSyntheticNodeIDs(root, events)
	fmt.Fprintf(&b, "## Synthetic Nodes Without Create Event\n\n")
	if len(orphanIDs) == 0 {
		fmt.Fprintf(&b, "- none\n")
	} else {
		for _, id := range orphanIDs {
			fmt.Fprintf(&b, "- `%s`\n", id)
		}
	}
	return os.WriteFile(path, []byte(b.String()), 0o644)
}

func countTrace(events []TraceEvent, key func(TraceEvent) string) map[string]int {
	counts := map[string]int{}
	for _, event := range events {
		value := key(event)
		if value == "" {
			value = "(empty)"
		}
		counts[value]++
	}
	return counts
}

func formatTraceCounts(counts map[string]int) string {
	if len(counts) == 0 {
		return "-"
	}
	keys := make([]string, 0, len(counts))
	for key := range counts {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	parts := make([]string, 0, len(keys))
	for _, key := range keys {
		parts = append(parts, fmt.Sprintf("%s:%d", key, counts[key]))
	}
	return strings.Join(parts, ", ")
}

func orphanSyntheticNodeIDs(root Node, events []TraceEvent) []string {
	created := map[string]bool{}
	for _, event := range events {
		if event.Decision != "create_group" {
			continue
		}
		for _, id := range event.OutputNodeIDs {
			created[id] = true
		}
	}
	var orphanIDs []string
	var walk func(Node)
	walk = func(node Node) {
		if node.Meta.Synthetic && node.ID != "" && !created[node.ID] {
			orphanIDs = append(orphanIDs, node.ID)
		}
		for _, child := range node.Children {
			walk(child)
		}
	}
	walk(root)
	sort.Strings(orphanIDs)
	return orphanIDs
}

func traceNodeIDs(nodes []Node) []string {
	ids := make([]string, 0, len(nodes))
	for _, node := range nodes {
		if node.ID != "" {
			ids = append(ids, node.ID)
		}
	}
	return ids
}

func traceNodeBBox(nodes []Node) *contract.BBox {
	if len(nodes) == 0 {
		return nil
	}
	box := unionNodeBBox(nodes)
	return &box
}

func traceBBoxValue(box contract.BBox) map[string]int {
	return map[string]int{
		"x":      box.X,
		"y":      box.Y,
		"width":  box.Width,
		"height": box.Height,
	}
}

func traceRound4(value float64) float64 {
	return round4(value)
}
