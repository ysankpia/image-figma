from __future__ import annotations

from pathlib import Path
from time import sleep

from fastapi.testclient import TestClient
from PIL import Image

from app.config import Settings
from app.main import create_app
from app.state import state
from app.storage import TaskStorage
from app.tasks import TaskManager

from .test_project_builder import write_fake_m29extract


def test_health() -> None:
    client = TestClient(create_app())
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "ok"


def test_project_api_upload_and_download(tmp_path: Path) -> None:
    configure_state(tmp_path)
    image_path = tmp_path / "input.png"
    Image.new("RGB", (64, 48), "#ffffff").save(image_path)

    client = TestClient(create_app())
    with image_path.open("rb") as handle:
        response = client.post(
            "/api/pencil/projects",
            data={"projectName": "API Project", "mode": "visual-fidelity", "columns": "1", "includeDebug": "true"},
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


def configure_state(tmp_path: Path) -> None:
    settings = Settings(
        addr="127.0.0.1:0",
        storage_root=tmp_path / "storage",
        m29extract_path=write_fake_m29extract(tmp_path),
        max_upload_bytes=1024 * 1024,
        max_files=20,
        max_workers=1,
        cors_allow_origins=["*"],
        ocr_provider="none",
    )
    state.settings = settings
    state.storage = TaskStorage(settings.storage_root)
    state.tasks = TaskManager(state.storage, settings)


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
