#!/usr/bin/env python3
import unittest

import compare_trees as ct


class CompareTreesIdentityTest(unittest.TestCase):
    def test_norm_codia_preserves_guid_identity_and_path(self):
        root = {
            "guid": {"sessionID": 1, "localID": 5},
            "type": "FRAME",
            "name": "Root",
            "size": {"x": 100, "y": 100},
            "transform": {"m02": 0, "m12": 0},
            "children": [
                {
                    "guid": {"sessionID": 1, "localID": 130},
                    "type": "FRAME",
                    "name": "Button",
                    "size": {"x": 20, "y": 10},
                    "transform": {"m02": 4, "m12": 8},
                    "children": [],
                }
            ],
        }

        normalized = ct.norm_codia(root)
        child = normalized["children"][0]

        self.assertEqual(normalized["id"], "codia:1:5")
        self.assertEqual(normalized["sourceId"], "1:5")
        self.assertEqual(normalized["path"], "")
        self.assertEqual(child["id"], "codia:1:130")
        self.assertEqual(child["sourceId"], "1:130")
        self.assertEqual(child["path"], "/0")
        self.assertEqual(child["parentId"], "codia:1:5")
        self.assertFalse(child["identityFallback"])

    def test_norm_go_preserves_source_id_and_parent_identity(self):
        root = {
            "id": "body_0001",
            "type": "Body",
            "bbox": {"x": 0, "y": 0, "width": 100, "height": 100},
            "children": [
                {
                    "id": "sgroup_0030",
                    "type": "Layer",
                    "bbox": {"x": 4, "y": 8, "width": 20, "height": 10},
                    "meta": {"groupKind": "text_background_group"},
                    "children": [],
                }
            ],
        }

        normalized = ct.norm_go(root)
        child = normalized["children"][0]

        self.assertEqual(normalized["id"], "go:body_0001")
        self.assertEqual(normalized["sourceId"], "body_0001")
        self.assertEqual(child["id"], "go:sgroup_0030")
        self.assertEqual(child["sourceId"], "sgroup_0030")
        self.assertEqual(child["path"], "/0")
        self.assertEqual(child["parentId"], "go:body_0001")
        self.assertEqual(child["groupKind"], "text_background_group")

    def test_grouping_eval_trace_reports_precision_f1_and_identities(self):
        codia = {
            "id": "codia:1:1",
            "sourceId": "1:1",
            "path": "",
            "parentId": "",
            "type": "FRAME",
            "name": "Root",
            "x": 0,
            "y": 0,
            "w": 100,
            "h": 100,
            "children": [
                {
                    "id": "codia:1:2",
                    "sourceId": "1:2",
                    "path": "/0",
                    "parentId": "codia:1:1",
                    "type": "FRAME",
                    "name": "Group",
                    "x": 10,
                    "y": 10,
                    "w": 40,
                    "h": 20,
                    "children": [
                        {"id": "codia:1:3", "sourceId": "1:3", "path": "/0/0", "parentId": "codia:1:2", "type": "TEXT", "name": "A", "x": 10, "y": 10, "w": 10, "h": 10, "children": []},
                        {"id": "codia:1:4", "sourceId": "1:4", "path": "/0/1", "parentId": "codia:1:2", "type": "TEXT", "name": "B", "x": 40, "y": 10, "w": 10, "h": 10, "children": []},
                    ],
                }
            ],
        }
        go = {
            "id": "go:body_0001",
            "sourceId": "body_0001",
            "path": "",
            "parentId": "",
            "type": "Body",
            "name": "Body",
            "groupKind": "",
            "x": 0,
            "y": 0,
            "w": 100,
            "h": 100,
            "children": [
                {
                    "id": "go:sgroup_0001",
                    "sourceId": "sgroup_0001",
                    "path": "/0",
                    "parentId": "go:body_0001",
                    "type": "Layer",
                    "name": "Groups",
                    "groupKind": "spatial_group",
                    "x": 10,
                    "y": 10,
                    "w": 40,
                    "h": 20,
                    "children": [
                        {"id": "go:a", "sourceId": "a", "path": "/0/0", "parentId": "go:sgroup_0001", "type": "Text", "name": "A", "groupKind": "", "x": 10, "y": 10, "w": 10, "h": 10, "children": []},
                        {"id": "go:b", "sourceId": "b", "path": "/0/1", "parentId": "go:sgroup_0001", "type": "Text", "name": "B", "groupKind": "", "x": 40, "y": 10, "w": 10, "h": 10, "children": []},
                    ],
                }
            ],
        }

        trace = ct.grouping_eval_trace(codia, go)
        summary = trace["summary"]

        self.assertEqual(summary["recall"], 1.0)
        self.assertEqual(summary["goPrecision"], 1.0)
        self.assertEqual(summary["f1"], 1.0)
        self.assertEqual(summary["containerRatio"], 1.0)
        self.assertEqual(trace["goContainers"][0]["normalizedNodeId"], "go:body_0001")
        self.assertEqual(trace["goContainers"][0]["bestCodia"]["normalizedNodeId"], "codia:1:1")


if __name__ == "__main__":
    unittest.main()
