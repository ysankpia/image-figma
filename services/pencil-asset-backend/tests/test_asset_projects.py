from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZipFile

from fastapi.testclient import TestClient
from PIL import Image

from app.config import Settings
from app.evidence import EvidenceResult
from app.main import create_app
from app.state import state


def test_health(tmp_path: Path) -> None:
    configure_state(tmp_path)
    client = TestClient(create_app())
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "ok"


def test_ready_requires_yolo_model(tmp_path: Path) -> None:
    configure_state(tmp_path, yolo_model_exists=False)
    client = TestClient(create_app())
    response = client.get("/api/ready")
    assert response.status_code == 503
    assert "PENCIL_ASSET_YOLO_MODEL" in json.dumps(response.json(), ensure_ascii=False)


def test_create_manual_export_and_download(tmp_path: Path, monkeypatch) -> None:
    configure_state(tmp_path)
    monkeypatch.setattr("app.projects.evidence.collect_page_evidence", fake_collect_page_evidence)
    image_path = write_image(tmp_path / "input.png", (96, 72))

    client = TestClient(create_app())
    with image_path.open("rb") as handle:
        response = client.post(
            "/api/asset-projects",
            data={"projectName": "Asset Project"},
            files=[("files[]", ("input.png", handle, "image/png"))],
        )
    assert response.status_code == 200
    created = response.json()["data"]
    project_id = created["projectId"]
    assert created["pageCount"] == 1
    assert created["candidateCount"] >= 1

    review = client.get(f"/api/asset-projects/{project_id}/review")
    assert review.status_code == 200
    assert "Pencil Asset Review" in review.text
    assert "manual-slices" in review.text

    candidates = client.get(f"/api/asset-projects/{project_id}/candidates").json()["data"]
    candidate = candidates["pages"][0]["candidates"][0]
    manual = {
        "schema": "pencil.manual_slices.v1",
        "projectName": "Asset Project",
        "pages": [
            {
                "pageId": "page_0001",
                "sourceImage": candidates["pages"][0]["sourceImage"],
                "width": 96,
                "height": 72,
                "slices": [
                    {
                        "id": "page_0001__slice_0001",
                        "name": "hero",
                        "displayName": "hero",
                        "kind": candidate["kind"],
                        "bbox": candidate["bbox"],
                        "selected": True,
                        "exportMode": "rect",
                        "source": "candidate_confirmed",
                        "candidateIds": [candidate["id"]],
                    }
                ],
            }
        ],
    }
    put_response = client.put(f"/api/asset-projects/{project_id}/manual-slices", json=manual)
    assert put_response.status_code == 200
    assert put_response.json()["data"]["selectedSliceCount"] == 1

    preview = client.post(f"/api/asset-projects/{project_id}/export-preview")
    assert preview.status_code == 200
    assert preview.json()["data"]["assetCount"] == 1

    export = client.post(f"/api/asset-projects/{project_id}/export")
    assert export.status_code == 200
    manifest = export.json()["data"]
    assert manifest["mode"] == "pencil-handoff"
    assert manifest["selectedAssetCount"] == 1
    assert manifest["refCheck"]["badRefs"] == 0
    assert manifest["refCheck"]["missingRefs"] == 0

    project_zip_response = client.get(f"/api/asset-projects/{project_id}/download.zip")
    selected_zip_response = client.get(f"/api/asset-projects/{project_id}/selected-assets.zip")
    assert project_zip_response.status_code == 200
    assert selected_zip_response.status_code == 200

    project_zip = tmp_path / "project.zip"
    selected_zip = tmp_path / "selected-assets.zip"
    project_zip.write_bytes(project_zip_response.content)
    selected_zip.write_bytes(selected_zip_response.content)
    with ZipFile(project_zip) as archive:
        names = set(archive.namelist())
        assert "design.pen" in names
        assert "manifest.json" in names
        assert "assets/visible/page_0001/slice_0001.png" in names
        assert "selected-assets.zip" not in names
        design = json.loads(archive.read("design.pen"))
        refs: list[str] = []
        collect_refs(design, refs)
        assert refs == ["./assets/visible/page_0001/slice_0001.png"]
    with ZipFile(selected_zip) as archive:
        names = set(archive.namelist())
        assert "page_0001/slice_0001.png" in names
        selected_manifest = json.loads(archive.read("manifest.json"))
        assert selected_manifest["assetCount"] == 1


def test_empty_export_returns_409(tmp_path: Path, monkeypatch) -> None:
    configure_state(tmp_path)
    monkeypatch.setattr("app.projects.evidence.collect_page_evidence", fake_collect_page_evidence)
    image_path = write_image(tmp_path / "input.png", (96, 72))
    client = TestClient(create_app())
    with image_path.open("rb") as handle:
        project_id = client.post(
            "/api/asset-projects",
            data={"projectName": "Empty"},
            files=[("files[]", ("input.png", handle, "image/png"))],
        ).json()["data"]["projectId"]
    assert client.post(f"/api/asset-projects/{project_id}/export-preview").status_code == 409
    assert client.post(f"/api/asset-projects/{project_id}/export").status_code == 409


def test_manual_validation_rejects_bad_kind_and_bounds(tmp_path: Path, monkeypatch) -> None:
    configure_state(tmp_path)
    monkeypatch.setattr("app.projects.evidence.collect_page_evidence", fake_collect_page_evidence)
    image_path = write_image(tmp_path / "input.png", (96, 72))
    client = TestClient(create_app())
    with image_path.open("rb") as handle:
        project_id = client.post(
            "/api/asset-projects",
            data={"projectName": "Invalid"},
            files=[("files[]", ("input.png", handle, "image/png"))],
        ).json()["data"]["projectId"]
    bad_kind = {
        "schema": "pencil.manual_slices.v1",
        "pages": [
            {
                "pageId": "page_0001",
                "slices": [
                    {"id": "s1", "kind": "text", "bbox": {"x": 0, "y": 0, "width": 10, "height": 10}},
                ],
            }
        ],
    }
    assert client.put(f"/api/asset-projects/{project_id}/manual-slices", json=bad_kind).status_code == 400
    out_of_bounds = {
        "schema": "pencil.manual_slices.v1",
        "pages": [
            {
                "pageId": "page_0001",
                "slices": [
                    {"id": "s1", "kind": "image", "bbox": {"x": 90, "y": 0, "width": 20, "height": 10}},
                ],
            }
        ],
    }
    assert client.put(f"/api/asset-projects/{project_id}/manual-slices", json=out_of_bounds).status_code == 400


def test_text_evidence_does_not_become_export_candidate(tmp_path: Path, monkeypatch) -> None:
    configure_state(tmp_path)
    monkeypatch.setattr("app.projects.evidence.collect_page_evidence", fake_text_only_evidence)
    image_path = write_image(tmp_path / "input.png", (96, 72))
    client = TestClient(create_app())
    with image_path.open("rb") as handle:
        response = client.post(
            "/api/asset-projects",
            data={"projectName": "Text Only"},
            files=[("files[]", ("input.png", handle, "image/png"))],
        )
    assert response.status_code == 500
    assert "no image/icon candidate evidence generated" in response.json()["detail"]


def configure_state(tmp_path: Path, *, yolo_model_exists: bool = True) -> None:
    model = tmp_path / "best.pt"
    if yolo_model_exists:
        model.write_bytes(b"fake model")
    state.settings = Settings(
        storage_root=tmp_path / "storage",
        max_upload_bytes=10 * 1024 * 1024,
        max_files=20,
        cors_allow_origins=["*"],
        yolo_model=model if yolo_model_exists else tmp_path / "missing.pt",
        yolo_conf=0.18,
        yolo_iou=0.45,
        yolo_imgsz=640,
        yolo_device="auto",
        m29extract_path=None,
        psdlike_root=tmp_path / "psdlike",
        ocr_provider="none",
    )


def fake_collect_page_evidence(**_: object) -> EvidenceResult:
    return EvidenceResult(
        evidence={
            "schema": "pencil_asset.evidence.v1",
            "pageId": "page_0001",
            "items": [
                {
                    "id": "page_0001__yolo_0001",
                    "source": "yolo",
                    "rawKind": "Image",
                    "kind": "image",
                    "bbox": {"x": 10, "y": 12, "width": 30, "height": 24},
                    "confidence": 0.91,
                    "reason": "yolo_detection",
                },
                {
                    "id": "page_0001__m29_0001",
                    "source": "m29",
                    "rawKind": "raster_region",
                    "kind": "image",
                    "bbox": {"x": 11, "y": 13, "width": 29, "height": 23},
                    "confidence": 0.62,
                    "reason": "m29_physical_evidence",
                },
                {
                    "id": "page_0001__ocr_0001",
                    "source": "ocr",
                    "rawKind": "text",
                    "kind": "text",
                    "bbox": {"x": 60, "y": 10, "width": 20, "height": 10},
                    "confidence": 0.8,
                    "reason": "ocr_text",
                },
            ],
        },
        warnings=["m29extract missing; skipped M29 evidence"],
    )


def fake_text_only_evidence(**_: object) -> EvidenceResult:
    return EvidenceResult(
        evidence={
            "schema": "pencil_asset.evidence.v1",
            "pageId": "page_0001",
            "items": [
                {
                    "id": "page_0001__ocr_0001",
                    "source": "ocr",
                    "rawKind": "text",
                    "kind": "text",
                    "bbox": {"x": 4, "y": 4, "width": 20, "height": 10},
                    "confidence": 0.8,
                    "reason": "ocr_text",
                }
            ],
        },
        warnings=[],
    )


def write_image(path: Path, size: tuple[int, int]) -> Path:
    Image.new("RGB", size, "#ffffff").save(path)
    return path


def collect_refs(node: object, refs: list[str]) -> None:
    if not isinstance(node, dict):
        return
    fill = node.get("fill")
    if isinstance(fill, dict) and fill.get("type") == "image":
        refs.append(str(fill["url"]))
    for child in node.get("children") or []:
        collect_refs(child, refs)
