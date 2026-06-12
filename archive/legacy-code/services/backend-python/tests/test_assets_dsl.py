import json

from PIL import Image

from app.crop import crop_image_assets
from app.dsl import build_dsl
from app.schema import BBox, DraftElement


def test_crop_image_assets_only_writes_image_assets(tmp_path):
    image = Image.new("RGB", (100, 100), "white")
    elements = [
        DraftElement("node_image_0001", "image", "icon", BBox(10, 10, 20, 20), 20001, 0.9, ["cand_0001"], "emit_image"),
        DraftElement("node_shape_0001", "shape", "card_bg", BBox(0, 0, 80, 40), 10001, 0.9, ["cand_0002"], "emit_shape"),
        DraftElement("node_text_0001", "text", "TextView", BBox(5, 5, 30, 12), 30001, 0.9, ["text_0001"], "emit_text", text="Hi"),
    ]

    asset_map = crop_image_assets(image, elements, str(tmp_path))

    assert asset_map == {"node_image_0001": "node_image_0001.png"}
    assert sorted(path.name for path in (tmp_path / "assets").iterdir()) == ["node_image_0001.png"]


def test_build_dsl_has_asset_refs_and_shape_has_no_asset():
    image = Image.new("RGB", (100, 100), "white")
    elements = [
        DraftElement("node_shape_0001", "shape", "card_bg", BBox(0, 0, 80, 40), 10001, 0.9, ["cand_0002"], "emit_shape", style={"fill": "#FFFFFF"}),
        DraftElement("node_image_0001", "image", "icon", BBox(10, 10, 20, 20), 20001, 0.9, ["cand_0001"], "emit_image"),
        DraftElement("node_text_0001", "text", "TextView", BBox(5, 5, 30, 12), 30001, 0.9, ["text_0001"], "emit_text", text="Hi", style={"fontSize": 10}),
    ]

    dsl = build_dsl(elements, {"node_image_0001": "node_image_0001.png"}, image, "task_test")

    children = dsl["root"]["children"]
    assert [child["type"] for child in children] == ["shape", "image", "text"]
    assert "image" not in children[0]
    assert children[1]["image"]["assetId"] == "asset_node_image_0001"
    assert dsl["assets"][0]["assetId"] == "asset_node_image_0001"
    json.dumps(dsl)
