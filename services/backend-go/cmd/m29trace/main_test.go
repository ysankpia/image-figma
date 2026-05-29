package main

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/visualtree"
)

func TestFindCreateEventPrefersCreateGroup(t *testing.T) {
	events := []visualtree.TraceEvent{
		{EventID: "evt_000001", Decision: "wrap", OutputNodeIDs: []string{"sgroup_0001"}},
		{EventID: "evt_000002", Decision: "create_group", OutputNodeIDs: []string{"sgroup_0001"}},
	}
	event, ok := findCreateEvent(events, "sgroup_0001")
	if !ok || event.EventID != "evt_000002" {
		t.Fatalf("expected create_group event, got %#v ok=%v", event, ok)
	}
}

func TestFindCreateEventRequiresCreateGroup(t *testing.T) {
	events := []visualtree.TraceEvent{
		{EventID: "evt_000001", Decision: "wrap", OutputNodeIDs: []string{"sgroup_0001"}},
	}
	if event, ok := findCreateEvent(events, "sgroup_0001"); ok {
		t.Fatalf("expected no create event, got %#v", event)
	}
}

func TestReadEvalTraceIndexesGoContainers(t *testing.T) {
	tmp := t.TempDir()
	path := filepath.Join(tmp, "eval.json")
	if err := os.WriteFile(path, []byte(`{"goContainers":[{"nodeId":"sgroup_0001","verdict":"extra","bestCodiaIoU":0.25}]}`), 0o644); err != nil {
		t.Fatal(err)
	}
	index, err := readEvalTrace(path)
	if err != nil {
		t.Fatal(err)
	}
	item, ok := index.ByNode["sgroup_0001"]
	if !ok || item.Verdict != "extra" || item.BestCodiaIoU != 0.25 {
		t.Fatalf("unexpected eval index: %#v", index.ByNode)
	}
}

func TestReadEvalTracePreservesIdentityFields(t *testing.T) {
	tmp := t.TempDir()
	path := filepath.Join(tmp, "eval.json")
	data := `{
		"goContainers": [{
			"nodeId": "sgroup_0030",
			"normalizedNodeId": "go:sgroup_0030",
			"sourceId": "sgroup_0030",
			"path": "/0/3",
			"parentNodeId": "go:token_0048",
			"verdict": "extra",
			"bestCodiaIoU": 0.3466,
			"bestCodia": {
				"codiaNodeId": "codia:1:130",
				"normalizedNodeId": "codia:1:130",
				"sourceId": "1:130",
				"path": "/0/3/4/2",
				"parentCodiaNodeId": "codia:1:128"
			}
		}]
	}`
	if err := os.WriteFile(path, []byte(data), 0o644); err != nil {
		t.Fatal(err)
	}
	index, err := readEvalTrace(path)
	if err != nil {
		t.Fatal(err)
	}
	item := index.ByNode["sgroup_0030"]
	if item.NormalizedNodeID != "go:sgroup_0030" || item.Path != "/0/3" || item.ParentNodeID != "go:token_0048" {
		t.Fatalf("unexpected go identity fields: %#v", item)
	}
	if stringMapValue(item.BestCodia, "codiaNodeId") != "codia:1:130" || stringMapValue(item.BestCodia, "path") != "/0/3/4/2" {
		t.Fatalf("unexpected codia identity fields: %#v", item.BestCodia)
	}
}
