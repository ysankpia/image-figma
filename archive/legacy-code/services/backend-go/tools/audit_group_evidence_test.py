#!/usr/bin/env python3
import json
import os
import tempfile
import unittest

import audit_group_evidence as audit


def write_json(path, value):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(value, f)


def write_jsonl(path, rows):
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


class AuditGroupEvidenceTest(unittest.TestCase):
    def test_records_join_tree_trace_and_eval(self):
        with tempfile.TemporaryDirectory() as tmp:
            tree_path = os.path.join(tmp, "visual_tree.v1.json")
            trace_path = os.path.join(tmp, "visual_tree_trace.v1.jsonl")
            eval_path = os.path.join(tmp, "visual_tree_eval_trace.json")
            write_json(tree_path, {
                "root": {
                    "id": "body_0001",
                    "type": "Body",
                    "bbox": {"x": 0, "y": 0, "width": 200, "height": 100},
                    "children": [
                        {
                            "id": "sgroup_0001",
                            "type": "Layer",
                            "bbox": {"x": 10, "y": 10, "width": 80, "height": 20},
                            "meta": {
                                "synthetic": True,
                                "groupKind": "spatial_group",
                                "parentReason": "xycut_y",
                                "groupRole": "structural",
                                "evidenceScore": 0.5,
                            },
                            "children": [
                                {
                                    "id": "text_0001",
                                    "type": "Text",
                                    "bbox": {"x": 10, "y": 10, "width": 30, "height": 20},
                                    "sourceRefs": {"relationIds": ["rel_0001"]},
                                },
                                {
                                    "id": "img_0001",
                                    "type": "Image",
                                    "bbox": {"x": 60, "y": 10, "width": 30, "height": 20},
                                },
                            ],
                        }
                    ],
                }
            })
            write_jsonl(trace_path, [
                {
                    "eventId": "evt_000001",
                    "operation": "spatial_group_create",
                    "decision": "create_group",
                    "decisionClass": "structural_candidate",
                    "spatialDepth": 1,
                    "outputNodeIds": ["sgroup_0001"],
                    "metrics": {"childCount": 2},
                }
            ])
            write_json(eval_path, {
                "goContainers": [
                    {
                        "nodeId": "sgroup_0001",
                        "normalizedNodeId": "go:sgroup_0001",
                        "verdict": "matched",
                        "bestCodiaIoU": 0.91,
                        "groupKind": "spatial_group",
                    }
                ]
            })

            records = audit.records_for_case(tree_path, trace_path, eval_path, "case")

        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertTrue(record["treeJoinFound"])
        self.assertTrue(record["createEventFound"])
        self.assertEqual(record["operation"], "spatial_group_create")
        self.assertEqual(record["parentReason"], "xycut_y")
        self.assertEqual(record["spatialDepth"], 1)
        self.assertEqual(record["childCount"], 2)
        self.assertEqual(record["leafCount"], 2)
        self.assertTrue(record["containsText"])
        self.assertTrue(record["containsImage"])
        self.assertEqual(record["shortSide"], 20)
        self.assertEqual(record["shortSideBin"], "009-020")
        self.assertEqual(record["areaRatio"], 0.08)
        self.assertEqual(record["areaRatioBin"], "0.05-0.15")
        self.assertEqual(record["childKindsKey"], "Text|Image")
        self.assertEqual(record["descendantSourceRelationRefs"], 1)

    def test_projection_no_text_backtest_counts_extra_and_matched_loss(self):
        records = [
            {
                "groupKind": "spatial_group",
                "parentReason": "xycut_y",
                "containsText": False,
                "shortSide": 8,
                "verdict": "extra",
            },
            {
                "groupKind": "spatial_group",
                "parentReason": "neighbor_component",
                "containsText": False,
                "shortSide": 18,
                "verdict": "matched",
            },
            {
                "groupKind": "spatial_group",
                "parentReason": "xycut_y",
                "containsText": True,
                "shortSide": 8,
                "verdict": "matched",
            },
            {
                "groupKind": "Layer",
                "parentReason": "",
                "containsText": False,
                "shortSide": 6,
                "verdict": "extra",
            },
        ]

        report = audit.backtest_rules(records)

        self.assertIn("projection_no_text_shortSide<=20", report)
        self.assertIn("layer_no_text_shortSide<=8", report)
        self.assertIn("any_no_text_shortSide<=8", report)
        self.assertIn("             2", report)
        self.assertIn("             1", report)


if __name__ == "__main__":
    unittest.main()
