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


if __name__ == "__main__":
    unittest.main()

