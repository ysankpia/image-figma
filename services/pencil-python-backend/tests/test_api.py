from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from time import sleep
from zipfile import ZipFile

from fastapi.testclient import TestClient
from PIL import Image

from app.config import Settings, parse_boundary_source
from app.main import create_app
from app.readiness import ocr_check
from app.state import state
from app.storage import TaskStorage
from app.tasks import TaskManager

from .test_project_builder import write_fake_m29extract


def test_health() -> None:
    client = TestClient(create_app())
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "ok"


def test_ready_reports_ok_when_dependencies_are_available(tmp_path: Path) -> None:
    configure_state(tmp_path, default_boundary_source="psdlike")
    write_fake_psdlike(tmp_path)

    client = TestClient(create_app())
    response = client.get("/api/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["ready"] is True
    checks = {check["name"]: check for check in body["data"]["checks"]}
    assert checks["psdlikeRunner"]["ok"] is True
    assert checks["defaultBoundarySource"]["detail"] == "psdlike"


def test_ready_reports_503_when_dependencies_are_missing(tmp_path: Path) -> None:
    configure_state(tmp_path, default_boundary_source="psdlike")

    client = TestClient(create_app())
    response = client.get("/api/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["success"] is False
    assert body["data"]["ready"] is False
    checks = {check["name"]: check for check in body["data"]["checks"]}
    assert checks["psdlikeRunner"]["ok"] is False
    assert "missing" in checks["psdlikeRunner"]["detail"]


def test_ready_requires_m29_when_default_boundary_source_needs_it(tmp_path: Path) -> None:
    configure_state(tmp_path, default_boundary_source="hybrid", missing_m29extract=True)
    write_fake_psdlike(tmp_path)

    client = TestClient(create_app())
    response = client.get("/api/ready")

    assert response.status_code == 503
    checks = {check["name"]: check for check in response.json()["data"]["checks"]}
    assert checks["m29extract"]["ok"] is False


def test_ocr_check_can_require_baidu_token(tmp_path: Path, monkeypatch) -> None:
    configure_state(tmp_path)
    state.settings = Settings(
        addr=state.settings.addr,
        storage_root=state.settings.storage_root,
        m29extract_path=state.settings.m29extract_path,
        psdlike_root=state.settings.psdlike_root,
        psdlike_tile_size=state.settings.psdlike_tile_size,
        default_boundary_source=state.settings.default_boundary_source,
        max_upload_bytes=state.settings.max_upload_bytes,
        max_files=state.settings.max_files,
        max_workers=state.settings.max_workers,
        cors_allow_origins=state.settings.cors_allow_origins,
        ocr_provider="baidu_ppocrv5",
    )
    monkeypatch.delenv("BAIDU_PADDLE_OCR_TOKEN", raising=False)

    assert ocr_check(state.settings)["ok"] is True
    strict = ocr_check(state.settings, require_baidu_token=True)
    assert strict["ok"] is False
    assert "BAIDU_PADDLE_OCR_TOKEN" in strict["detail"]


def test_project_api_upload_and_download(tmp_path: Path) -> None:
    configure_state(tmp_path)
    image_path = tmp_path / "input.png"
    Image.new("RGB", (64, 48), "#ffffff").save(image_path)

    client = TestClient(create_app())
    with image_path.open("rb") as handle:
        response = client.post(
            "/api/pencil/projects",
            data={
                "projectName": "API Project",
                "mode": "visual-fidelity",
                "columns": "1",
                "includeDebug": "true",
                "boundarySource": "m29",
            },
            files=[("files[]", ("input.png", handle, "image/png"))],
        )
    assert response.status_code == 200
    task_id = response.json()["data"]["taskId"]

    status = wait_for_completion(client, task_id)
    assert status["status"] == "completed"
    assert status["pageCount"] == 1
    assert status["modes"] == ["visual-fidelity"]

    manifest_response = client.get(f"/api/pencil/projects/{task_id}/manifest")
    assert manifest_response.status_code == 200
    assert manifest_response.json()["data"]["pageCount"] == 1
    download_response = client.get(f"/api/pencil/projects/{task_id}/download.zip")
    assert download_response.status_code == 200
    assert download_response.content[:2] == b"PK"


def test_project_api_uses_configured_default_boundary_source(tmp_path: Path) -> None:
    configure_state(tmp_path, default_boundary_source="m29")
    image_path = tmp_path / "input.png"
    Image.new("RGB", (64, 48), "#ffffff").save(image_path)

    client = TestClient(create_app())
    with image_path.open("rb") as handle:
        response = client.post(
            "/api/pencil/projects",
            data={"projectName": "Default Boundary", "mode": "visual-fidelity", "columns": "1"},
            files=[("files[]", ("input.png", handle, "image/png"))],
        )
    assert response.status_code == 200
    assert response.json()["data"]["boundarySource"] == "m29"
    task_id = response.json()["data"]["taskId"]

    status = wait_for_completion(client, task_id)
    assert status["boundarySource"] == "m29"


def test_slice_project_api_review_manual_export_and_download(tmp_path: Path) -> None:
    configure_state(tmp_path, default_boundary_source="m29")
    image_path = tmp_path / "slice-input.png"
    Image.new("RGB", (96, 72), "#ffffff").save(image_path)

    client = TestClient(create_app())
    with image_path.open("rb") as handle:
        response = client.post(
            "/api/pencil/slice-projects",
            data={"projectName": "Slice Project", "includeDebug": "true", "boundarySource": "m29"},
            files=[("files[]", ("slice-input.png", handle, "image/png"))],
        )
    assert response.status_code == 200
    created = response.json()["data"]
    project_id = created["projectId"]
    assert created["manualSlicesConfirmed"] is False
    assert created["pageCount"] == 1

    review = client.get(f"/api/pencil/slice-projects/{project_id}/review")
    assert review.status_code == 200
    assert "Pencil Assisted Slice Workbench" in review.text
    assert "resizeBox" in review.text
    assert "fitToScreen" in review.text
    assert "filteredCandidates" in review.text

    project_response = client.get(f"/api/pencil/slice-projects/{project_id}")
    assert project_response.status_code == 200
    assert project_response.json()["data"]["pages"][0]["pageId"] == "page_0001"

    early_export = client.post(f"/api/pencil/slice-projects/{project_id}/export")
    assert early_export.status_code == 409
    assert "must be saved" in early_export.json()["detail"]

    candidates_response = client.get(f"/api/pencil/slice-projects/{project_id}/candidates")
    assert candidates_response.status_code == 200
    candidates = candidates_response.json()["data"]
    assert candidates["schema"] == "pencil.slice_candidates.v1"
    assert candidates["pages"][0]["candidates"]

    manual_slices = {
        "schema": "pencil.manual_slices.v1",
        "projectName": "Slice Project",
        "pages": [
            {
                "pageId": "page_0001",
                "sourceImage": "will_be_normalized.png",
                "width": 0,
                "height": 0,
                "slices": [
                    {
                        "id": "page_0001__slice_0001",
                        "name": "hero asset",
                        "kind": "image",
                        "bbox": {"x": 4, "y": 6, "width": 32, "height": 24},
                        "selected": True,
                        "exportMode": "rect",
                        "source": "manual",
                        "candidateIds": [],
                    }
                ],
            }
        ],
    }
    put_response = client.put(f"/api/pencil/slice-projects/{project_id}/manual-slices", json=manual_slices)
    assert put_response.status_code == 200
    assert put_response.json()["data"]["selectedSliceCount"] == 1
    confirmed = client.get(f"/api/pencil/slice-projects/{project_id}")
    assert confirmed.json()["data"]["manualSlicesConfirmed"] is True

    export_response = client.post(f"/api/pencil/slice-projects/{project_id}/export")
    assert export_response.status_code == 200
    manifest = export_response.json()["data"]
    assert manifest["selectedAssetCount"] == 1

    download_response = client.get(f"/api/pencil/slice-projects/{project_id}/download.zip")
    assert download_response.status_code == 200
    zip_path = tmp_path / "download.zip"
    zip_path.write_bytes(download_response.content)
    with ZipFile(zip_path) as archive:
        names = set(archive.namelist())
        selected_zip_bytes = archive.read("selected-assets.zip")
        for mode in ("clean-editable", "visual-fidelity", "visual-ocr"):
            design = json.loads(archive.read(f"{mode}/design.pen"))
            serialized = json.dumps(design)
            for banned in ("source.png", "raw-crops", "masks/", "debug/", "../"):
                assert banned not in serialized
            for url in collect_image_urls(design["children"]):
                assert url.startswith("./assets/visible/")
                assert not Path(url).is_absolute()
                assert f"{mode}/{url.removeprefix('./')}" in names
    assert "manifest.json" in names
    assert "selected-assets.zip" in names
    assert "clean-editable/design.pen" in names
    assert any(name.startswith("clean-editable/assets/visible/page_0001/") for name in names)
    assert not any(name.startswith("selected-assets/page_0001/") for name in names)

    with ZipFile(BytesIO(selected_zip_bytes)) as selected_archive:
        selected_names = set(selected_archive.namelist())
    assert "manifest.json" in selected_names
    assert len([name for name in selected_names if name.startswith("page_0001/") and name.endswith(".png")]) == 1


def test_slice_project_new_page_returns_upload_workbench_html(tmp_path: Path) -> None:
    configure_state(tmp_path, default_boundary_source="m29")
    client = TestClient(create_app())

    response = client.get("/api/pencil/slice-projects/new")

    assert response.status_code == 200
    assert "Pencil Slice Review" in response.text
    assert 'name="files[]"' in response.text
    assert "boundarySource" in response.text
    assert "/api/pencil/slice-projects" in response.text


def test_slice_project_api_accepts_three_images(tmp_path: Path) -> None:
    configure_state(tmp_path, default_boundary_source="m29")
    image_paths = []
    for index in range(3):
        path = tmp_path / f"slice-input-{index}.png"
        Image.new("RGB", (64 + index * 4, 48 + index * 4), "#ffffff").save(path)
        image_paths.append(path)

    client = TestClient(create_app())
    handles = [path.open("rb") for path in image_paths]
    try:
        response = client.post(
            "/api/pencil/slice-projects",
            data={"projectName": "Slice Multi", "boundarySource": "m29"},
            files=[("files[]", (path.name, handle, "image/png")) for path, handle in zip(image_paths, handles, strict=True)],
        )
    finally:
        for handle in handles:
            handle.close()

    assert response.status_code == 200
    project_id = response.json()["data"]["projectId"]
    candidates = client.get(f"/api/pencil/slice-projects/{project_id}/candidates").json()["data"]
    assert [page["pageId"] for page in candidates["pages"]] == ["page_0001", "page_0002", "page_0003"]
    manual = client.get(f"/api/pencil/slice-projects/{project_id}/manual-slices").json()["data"]
    assert [page["pageId"] for page in manual["pages"]] == ["page_0001", "page_0002", "page_0003"]


def test_slice_project_rejects_zero_selected_export(tmp_path: Path) -> None:
    configure_state(tmp_path, default_boundary_source="m29")
    image_path = tmp_path / "slice-input.png"
    Image.new("RGB", (64, 48), "#ffffff").save(image_path)

    client = TestClient(create_app())
    with image_path.open("rb") as handle:
        response = client.post(
            "/api/pencil/slice-projects",
            data={"projectName": "Slice Empty", "boundarySource": "m29"},
            files=[("files[]", ("slice-input.png", handle, "image/png"))],
        )
    project_id = response.json()["data"]["projectId"]
    manual_slices = {
        "schema": "pencil.manual_slices.v1",
        "projectName": "Slice Empty",
        "pages": [{"pageId": "page_0001", "slices": []}],
    }

    put_response = client.put(f"/api/pencil/slice-projects/{project_id}/manual-slices", json=manual_slices)
    assert put_response.status_code == 200
    assert put_response.json()["data"]["selectedSliceCount"] == 0

    export_response = client.post(f"/api/pencil/slice-projects/{project_id}/export")
    assert export_response.status_code == 409
    assert "no selected slices" in export_response.json()["detail"]


def test_slice_project_rejects_out_of_bounds_manual_slice(tmp_path: Path) -> None:
    configure_state(tmp_path, default_boundary_source="m29")
    image_path = tmp_path / "slice-input.png"
    Image.new("RGB", (64, 48), "#ffffff").save(image_path)

    client = TestClient(create_app())
    with image_path.open("rb") as handle:
        response = client.post(
            "/api/pencil/slice-projects",
            data={"projectName": "Slice Error", "boundarySource": "m29"},
            files=[("files[]", ("slice-input.png", handle, "image/png"))],
        )
    project_id = response.json()["data"]["projectId"]
    manual_slices = {
        "schema": "pencil.manual_slices.v1",
        "projectName": "Slice Error",
        "pages": [
            {
                "pageId": "page_0001",
                "slices": [
                    {
                        "id": "bad",
                        "name": "bad",
                        "kind": "image",
                        "bbox": {"x": 60, "y": 40, "width": 20, "height": 20},
                        "exportMode": "rect",
                    }
                ],
            }
        ],
    }

    put_response = client.put(f"/api/pencil/slice-projects/{project_id}/manual-slices", json=manual_slices)
    assert put_response.status_code == 400
    assert "out of bounds" in put_response.json()["detail"]


def test_slice_project_rejects_missing_and_invalid_uploads(tmp_path: Path) -> None:
    configure_state(tmp_path, default_boundary_source="m29")
    client = TestClient(create_app())

    no_files = client.post("/api/pencil/slice-projects", data={"projectName": "No Files"})
    assert no_files.status_code == 400
    assert "files[] is required" in no_files.json()["detail"]

    bad_image = tmp_path / "bad.png"
    bad_image.write_bytes(b"not an image")
    with bad_image.open("rb") as handle:
        invalid = client.post(
            "/api/pencil/slice-projects",
            data={"projectName": "Bad Image"},
            files=[("files[]", ("bad.png", handle, "image/png"))],
        )
    assert invalid.status_code == 400
    assert "invalid image" in invalid.json()["detail"]


def test_slice_project_missing_project_errors(tmp_path: Path) -> None:
    configure_state(tmp_path, default_boundary_source="m29")
    client = TestClient(create_app())

    missing = "slice_missing"
    assert client.get(f"/api/pencil/slice-projects/{missing}").status_code == 404
    assert client.get(f"/api/pencil/slice-projects/{missing}/review").status_code == 404
    assert client.post(f"/api/pencil/slice-projects/{missing}/export").status_code == 404
    assert client.get(f"/api/pencil/slice-projects/{missing}/download.zip").status_code == 404


def test_parse_boundary_source_accepts_supported_values() -> None:
    assert parse_boundary_source("psdlike") == "psdlike"
    assert parse_boundary_source("M29") == "m29"
    assert parse_boundary_source(" hybrid ") == "hybrid"


def test_parse_boundary_source_rejects_unknown_value() -> None:
    try:
        parse_boundary_source("bad")
    except ValueError as error:
        assert "unsupported boundarySource" in str(error)
    else:
        raise AssertionError("expected ValueError")


def configure_state(
    tmp_path: Path,
    *,
    default_boundary_source: str = "m29",
    missing_m29extract: bool = False,
) -> None:
    m29extract_path = None if missing_m29extract else write_fake_m29extract(tmp_path)
    settings = Settings(
        addr="127.0.0.1:0",
        storage_root=tmp_path / "storage",
        m29extract_path=m29extract_path,
        psdlike_root=tmp_path / "psdlike",
        psdlike_tile_size=8,
        default_boundary_source=parse_boundary_source(default_boundary_source),
        max_upload_bytes=1024 * 1024,
        max_files=20,
        max_workers=1,
        cors_allow_origins=["*"],
        ocr_provider="none",
    )
    state.settings = settings
    state.storage = TaskStorage(settings.storage_root)
    state.tasks = TaskManager(state.storage, settings)


def write_fake_psdlike(tmp_path: Path) -> Path:
    root = tmp_path / "psdlike"
    tools = root / "tools"
    tools.mkdir(parents=True)
    (tools / "run_one.py").write_text("print('ok')\n", encoding="utf-8")
    (root / "pyproject.toml").write_text("[project]\nname='fake-psdlike'\n", encoding="utf-8")
    return root


def wait_for_completion(client: TestClient, task_id: str) -> dict[str, object]:
    for _ in range(100):
        response = client.get(f"/api/pencil/projects/{task_id}")
        assert response.status_code == 200
        data = response.json()["data"]
        if data["status"] in {"completed", "failed"}:
            assert data["status"] == "completed", data
            return data
        sleep(0.05)
    raise AssertionError("task did not complete")


def collect_image_urls(nodes: list[dict[str, object]]) -> list[str]:
    urls: list[str] = []
    for node in nodes:
        fill = node.get("fill")
        if isinstance(fill, dict) and fill.get("type") == "image":
            urls.append(str(fill.get("url") or ""))
        children = node.get("children")
        if isinstance(children, list):
            urls.extend(collect_image_urls(children))
    return urls
