package main

import (
	"bufio"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"sort"
	"strings"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/visualtree"
)

type evalTrace struct {
	GoContainers []evalGoContainer `json:"goContainers"`
}

type evalGoContainer struct {
	NodeID           string         `json:"nodeId"`
	NormalizedNodeID string         `json:"normalizedNodeId"`
	SourceID         string         `json:"sourceId"`
	Path             string         `json:"path"`
	ParentNodeID     string         `json:"parentNodeId"`
	GroupKind        string         `json:"groupKind"`
	Verdict          string         `json:"verdict"`
	BestCodiaIoU     float64        `json:"bestCodiaIoU"`
	BestCodia        map[string]any `json:"bestCodia,omitempty"`
}

func main() {
	tracePath := flag.String("trace", "", "path to visual_tree_trace.v1.jsonl")
	evalPath := flag.String("eval", "", "optional path to visual_tree_eval_trace.json")
	nodeID := flag.String("node", "", "node id to explain")
	summary := flag.Bool("summary", false, "print trace summary")
	flag.Parse()

	if *tracePath == "" {
		fmt.Fprintln(os.Stderr, "m29trace: missing -trace")
		os.Exit(2)
	}
	events, err := readTraceEvents(*tracePath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "m29trace: %v\n", err)
		os.Exit(1)
	}
	if *summary {
		printSummary(events)
		return
	}
	if *nodeID == "" {
		fmt.Fprintln(os.Stderr, "m29trace: provide -summary or -node")
		os.Exit(2)
	}

	event, ok := findCreateEvent(events, *nodeID)
	if !ok {
		fmt.Fprintf(os.Stderr, "m29trace: no create event for node %q\n", *nodeID)
		os.Exit(1)
	}
	fmt.Printf("node: %s\n", *nodeID)
	fmt.Printf("event: %s\n", event.EventID)
	fmt.Printf("operation: %s\n", event.Operation)
	fmt.Printf("decision: %s\n", event.Decision)
	fmt.Printf("decisionClass: %s\n", event.DecisionClass)
	fmt.Printf("groupKind: %s\n", event.GroupKind)
	fmt.Printf("parent: %s\n", event.ParentNodeID)
	fmt.Printf("spatialDepth: %d\n", event.SpatialDepth)
	fmt.Printf("reason: %s\n", event.Reason)
	fmt.Printf("inputNodes: %s\n", strings.Join(event.InputNodeIDs, ","))
	fmt.Printf("outputNodes: %s\n", strings.Join(event.OutputNodeIDs, ","))
	printJSONField("metrics", event.Metrics)
	printJSONField("thresholds", event.Thresholds)
	printJSONField("sourceEvidence", event.SourceEvidence)

	if *evalPath != "" {
		eval, err := readEvalTrace(*evalPath)
		if err != nil {
			fmt.Fprintf(os.Stderr, "m29trace: %v\n", err)
			os.Exit(1)
		}
		if goEval, ok := eval.ByNode[*nodeID]; ok {
			fmt.Printf("evalVerdict: %s\n", goEval.Verdict)
			printOptionalLine("goPath", goEval.Path)
			printOptionalLine("goParentNodeId", goEval.ParentNodeID)
			fmt.Printf("bestCodiaIoU: %.4f\n", goEval.BestCodiaIoU)
			printOptionalLine("bestCodiaNodeId", stringMapValue(goEval.BestCodia, "codiaNodeId"))
			printOptionalLine("bestCodiaPath", stringMapValue(goEval.BestCodia, "path"))
			printOptionalLine("bestCodiaParentNodeId", stringMapValue(goEval.BestCodia, "parentCodiaNodeId"))
			printJSONField("bestCodia", goEval.BestCodia)
		} else {
			fmt.Printf("evalVerdict: missing\n")
		}
	}
}

func readTraceEvents(path string) ([]visualtree.TraceEvent, error) {
	file, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer file.Close()
	var events []visualtree.TraceEvent
	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" {
			continue
		}
		var event visualtree.TraceEvent
		if err := json.Unmarshal([]byte(line), &event); err != nil {
			return nil, err
		}
		events = append(events, event)
	}
	if err := scanner.Err(); err != nil {
		return nil, err
	}
	return events, nil
}

func findCreateEvent(events []visualtree.TraceEvent, nodeID string) (visualtree.TraceEvent, bool) {
	for _, event := range events {
		if event.Decision == "create_group" && containsString(event.OutputNodeIDs, nodeID) {
			return event, true
		}
	}
	return visualtree.TraceEvent{}, false
}

func printSummary(events []visualtree.TraceEvent) {
	fmt.Printf("events: %d\n", len(events))
	printCounts("operations", events, func(event visualtree.TraceEvent) string { return event.Operation })
	printCounts("decisions", events, func(event visualtree.TraceEvent) string { return event.Decision })
	printCounts("decisionClasses", events, func(event visualtree.TraceEvent) string { return event.DecisionClass })
	printCounts("groupKinds", events, func(event visualtree.TraceEvent) string { return event.GroupKind })
	for _, event := range events {
		if event.Operation == "synthetic_orphan_check" {
			printJSONField("syntheticOrphanCheck", event.Metrics)
			printJSONField("syntheticOrphans", event.SourceEvidence)
			return
		}
	}
	fmt.Printf("syntheticOrphanCheck: unavailable\n")
}

func printCounts(label string, events []visualtree.TraceEvent, key func(visualtree.TraceEvent) string) {
	counts := map[string]int{}
	for _, event := range events {
		value := key(event)
		if value == "" {
			value = "(empty)"
		}
		counts[value]++
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
	fmt.Printf("%s: %s\n", label, strings.Join(parts, ", "))
}

type evalIndex struct {
	ByNode map[string]evalGoContainer
}

func readEvalTrace(path string) (evalIndex, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return evalIndex{}, err
	}
	var trace evalTrace
	if err := json.Unmarshal(data, &trace); err != nil {
		return evalIndex{}, err
	}
	index := evalIndex{ByNode: map[string]evalGoContainer{}}
	for _, item := range trace.GoContainers {
		index.ByNode[item.NodeID] = item
	}
	return index, nil
}

func printJSONField(label string, value any) {
	if value == nil {
		return
	}
	data, err := json.Marshal(value)
	if err != nil {
		fmt.Printf("%s: <unprintable>\n", label)
		return
	}
	fmt.Printf("%s: %s\n", label, string(data))
}

func printOptionalLine(label string, value string) {
	if value == "" {
		return
	}
	fmt.Printf("%s: %s\n", label, value)
}

func stringMapValue(values map[string]any, key string) string {
	if values == nil {
		return ""
	}
	value, ok := values[key]
	if !ok {
		return ""
	}
	text, ok := value.(string)
	if !ok {
		return ""
	}
	return text
}

func containsString(values []string, target string) bool {
	for _, value := range values {
		if value == target {
			return true
		}
	}
	return false
}
