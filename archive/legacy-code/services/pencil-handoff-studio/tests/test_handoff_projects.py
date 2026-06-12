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


def test_health_and_ready_without_yolo(tmp_path: Path) -> None:
    configure_state(tmp_path)
    client = TestClient(create_app())
    assert client.get("/api/health").status_code == 200
    ready = client.get("/api/ready")
    assert ready.status_code == 200
    checks = ready.json()["data"]["checks"]
    assert any(check["name"] == "yolo" and check["ok"] is False for check in checks)


def test_create_project_without_evidence_still_allows_manual_export(tmp_path: Path, monkeypatch) -> None:
    configure_state(tmp_path)
    monkeypatch.setattr("app.projects.evidence.collect_page_evidence", fake_empty_evidence)
    image_path = write_image(tmp_path / "input.png", (120, 90))
    client = TestClient(create_app())
    with image_path.open("rb") as handle:
        response = client.post(
            "/api/handoff-projects",
            data={"projectName": "Handoff", "includeOcr": "true", "includeBasicElements": "true"},
            files=[("files[]", ("input.png", handle, "image/png"))],
        )
    assert response.status_code == 200
    created = response.json()["data"]
    project_id = created["projectId"]
    assert created["pageCount"] == 1
    assert created["candidateCount"] == 0
    assert "no detectors available" in created["warnings"]

    candidates = client.get(f"/api/handoff-projects/{project_id}/candidates").json()["data"]
    manual = {
        "schema": "pencil.manual_slices.v1",
        "projectName": "Handoff",
        "pages": [
            {
                "pageId": "page_0001",
                "sourceImage": candidates["pages"][0]["sourceImage"],
                "width": 120,
                "height": 90,
                "slices": [
                    {
                        "id": "page_0001__slice_0001",
                        "pageId": "page_0001",
                        "name": "hero",
                        "displayName": "hero",
                        "kind": "image",
                        "bbox": {"x": 10, "y": 12, "width": 40, "height": 30},
                        "selected": True,
                        "source": "manual",
                        "candidateIds": [],
                        "tags": [],
                    },
                    {
                        "id": "page_0001__slice_0002",
                        "pageId": "page_0001",
                        "name": "basic",
                        "displayName": "basic",
                        "kind": "basic",
                        "bbox": {"x": 60, "y": 20, "width": 30, "height": 20},
                        "selected": True,
                        "source": "manual",
                        "candidateIds": [],
                        "tags": [],
                    },
                ],
            }
        ],
    }
    saved = client.put(f"/api/handoff-projects/{project_id}/manual-slices", json=manual)
    assert saved.status_code == 200
    assert saved.json()["data"]["selectedSliceCount"] == 2

    preview = client.post(f"/api/handoff-projects/{project_id}/export-preview")
    assert preview.status_code == 200
    assert preview.json()["data"]["assetCount"] == 2

    export = client.post(f"/api/handoff-projects/{project_id}/export")
    assert export.status_code == 200
    manifest = export.json()["data"]
    assert manifest["assetCount"] == 2
    assert manifest["originalCount"] == 1
    assert manifest["refCheck"]["badRefs"] == 0
    assert manifest["refCheck"]["missingRefs"] == 0

    project_zip_response = client.get(f"/api/handoff-projects/{project_id}/project.zip")
    assets_zip_response = client.get(f"/api/handoff-projects/{project_id}/assets.zip")
    assert project_zip_response.status_code == 200
    assert assets_zip_response.status_code == 200

    project_zip = tmp_path / "project.zip"
    assets_zip = tmp_path / "assets.zip"
    project_zip.write_bytes(project_zip_response.content)
    assets_zip.write_bytes(assets_zip_response.content)
    with ZipFile(project_zip) as archive:
        names = set(archive.namelist())
        assert "design.pen" in names
        assert "assets/originals/page_0001.png" in names
        assert "assets/slices/page_0001/slice_0001.png" in names
        assert "assets/slices/page_0001/slice_0002.png" in names
        assert "manual_slices.v1.json" in names
        design = json.loads(archive.read("design.pen"))
        refs: list[str] = []
        collect_refs(design, refs)
        assert "./assets/originals/page_0001.png" in refs
        assert "./assets/slices/page_0001/slice_0001.png" in refs
        assert "./assets/slices/page_0001/slice_0002.png" not in refs
        reference = design["children"][0]["children"][0]
        assert reference["locked"] is True
        assert reference["opacity"] == 0.45
    with ZipFile(assets_zip) as archive:
        names = set(archive.namelist())
        assert "originals/page_0001.png" in names
        assert "slices/page_0001/slice_0001.png" in names
        assert "slices/page_0001/slice_0002.png" in names
        assets_manifest = json.loads(archive.read("manifest.json"))
        assert assets_manifest["originalCount"] == 1
        assert assets_manifest["sliceCount"] == 2


def test_multi_upload_and_review_state(tmp_path: Path, monkeypatch) -> None:
    configure_state(tmp_path)
    monkeypatch.setattr("app.projects.evidence.collect_page_evidence", fake_candidate_evidence)
    image_a = write_image(tmp_path / "a.png", (100, 80))
    image_b = write_image(tmp_path / "b.png", (90, 70))
    client = TestClient(create_app())
    with image_a.open("rb") as a, image_b.open("rb") as b:
        response = client.post(
            "/api/handoff-projects",
            data={"projectName": "Multi"},
            files=[("files[]", ("a.png", a, "image/png")), ("files[]", ("b.png", b, "image/png"))],
        )
    assert response.status_code == 200
    project_id = response.json()["data"]["projectId"]
    assert response.json()["data"]["pageCount"] == 2
    assert response.json()["data"]["candidateCount"] == 2

    candidates = client.get(f"/api/handoff-projects/{project_id}/candidates").json()["data"]
    candidate_id = candidates["pages"][0]["candidates"][0]["id"]
    review_state = client.get(f"/api/handoff-projects/{project_id}/review-state").json()["data"]
    review_state["pages"][0]["hiddenCandidateIds"] = [candidate_id]
    review_state["filters"]["colors"]["selected"] = "#ff00ff"
    review_state["viewport"] = {"x": 10, "y": 20, "scale": 0.5}
    saved = client.put(f"/api/handoff-projects/{project_id}/review-state", json=review_state)
    assert saved.status_code == 200
    persisted = client.get(f"/api/handoff-projects/{project_id}/review-state").json()["data"]
    assert persisted["pages"][0]["hiddenCandidateIds"] == [candidate_id]
    assert persisted["filters"]["colors"]["selected"] == "#ff00ff"
    assert persisted["viewport"]["scale"] == 0.5

    bad = dict(persisted)
    bad["pages"] = [dict(persisted["pages"][0], hiddenCandidateIds=["missing"])]
    assert client.put(f"/api/handoff-projects/{project_id}/review-state", json=bad).status_code == 400


def test_validation_rejects_invalid_manual_slices(tmp_path: Path, monkeypatch) -> None:
    configure_state(tmp_path)
    monkeypatch.setattr("app.projects.evidence.collect_page_evidence", fake_empty_evidence)
    image_path = write_image(tmp_path / "input.png", (120, 90))
    client = TestClient(create_app())
    with image_path.open("rb") as handle:
        project_id = client.post(
            "/api/handoff-projects",
            data={"projectName": "Invalid"},
            files=[("files[]", ("input.png", handle, "image/png"))],
        ).json()["data"]["projectId"]
    bad_kind = {
        "schema": "pencil.manual_slices.v1",
        "projectName": "Invalid",
        "pages": [
            {
                "pageId": "page_0001",
                "slices": [
                    {"id": "s1", "name": "text", "kind": "text", "bbox": {"x": 0, "y": 0, "width": 10, "height": 10}},
                ],
            }
        ],
    }
    assert client.put(f"/api/handoff-projects/{project_id}/manual-slices", json=bad_kind).status_code == 400
    out_of_bounds = {
        "schema": "pencil.manual_slices.v1",
        "projectName": "Invalid",
        "pages": [
            {
                "pageId": "page_0001",
                "slices": [
                    {"id": "s1", "name": "bad", "kind": "image", "bbox": {"x": 110, "y": 0, "width": 20, "height": 10}},
                ],
            }
        ],
    }
    assert client.put(f"/api/handoff-projects/{project_id}/manual-slices", json=out_of_bounds).status_code == 400


def test_empty_export_returns_409(tmp_path: Path, monkeypatch) -> None:
    configure_state(tmp_path)
    monkeypatch.setattr("app.projects.evidence.collect_page_evidence", fake_empty_evidence)
    image_path = write_image(tmp_path / "input.png", (120, 90))
    client = TestClient(create_app())
    with image_path.open("rb") as handle:
        project_id = client.post(
            "/api/handoff-projects",
            data={"projectName": "Empty"},
            files=[("files[]", ("input.png", handle, "image/png"))],
        ).json()["data"]["projectId"]
    assert client.post(f"/api/handoff-projects/{project_id}/export-preview").status_code == 409
    assert client.post(f"/api/handoff-projects/{project_id}/export").status_code == 409


def configure_state(tmp_path: Path) -> None:
    state.settings = Settings(
        storage_root=tmp_path / "storage",
        max_upload_bytes=1024 * 1024,
        max_files=0,
        cors_allow_origins=["*"],
        yolo_model=None,
        yolo_conf=0.18,
        yolo_iou=0.45,
        yolo_imgsz=640,
        yolo_device="auto",
        m29extract_path=None,
        psdlike_root=tmp_path / "missing-psdlike",
        ocr_provider="none",
    )


def write_image(path: Path, size: tuple[int, int]) -> Path:
    image = Image.new("RGBA", size, (240, 240, 240, 255))
    image.save(path)
    return path


def fake_empty_evidence(**kwargs) -> EvidenceResult:
    return EvidenceResult(
        evidence={"schema": "pencil_handoff.evidence.v1", "pageId": kwargs["page_id"], "items": [], "warnings": ["no detectors available"]},
        warnings=["no detectors available"],
    )


def fake_candidate_evidence(**kwargs) -> EvidenceResult:
    page_id = kwargs["page_id"]
    item = {
        "id": f"{page_id}__fake_0001",
        "source": "fake",
        "rawKind": "image",
        "kind": "image",
        "bbox": {"x": 10, "y": 10, "width": 30, "height": 24},
        "confidence": 0.9,
        "reason": "fake",
    }
    return EvidenceResult(
        evidence={"schema": "pencil_handoff.evidence.v1", "pageId": page_id, "items": [item], "warnings": []},
        warnings=[],
    )


def collect_refs(value, refs: list[str]) -> None:
    if isinstance(value, dict):
        fill = value.get("fill")
        if isinstance(fill, dict) and fill.get("type") == "image":
            refs.append(fill["url"])
        for child in value.values():
            collect_refs(child, refs)
    elif isinstance(value, list):
        for item in value:
            collect_refs(item, refs)
