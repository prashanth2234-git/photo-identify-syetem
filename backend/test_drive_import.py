import asyncio
import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.database import db
from app.models import CreateEventRequest
from app.services import drive_service, import_service, photo_pipeline
from app.services.drive_service import DriveAccessError, DriveConfigError

client = TestClient(app)

VALID_PNG = None


def _valid_png_bytes() -> bytes:
    global VALID_PNG
    if VALID_PNG is None:
        img = Image.new("RGB", (64, 64), (120, 40, 200))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        VALID_PNG = buf.getvalue()
    return VALID_PNG


def _make_event() -> str:
    ev = db.create_event(
        CreateEventRequest(
            title="Drive Import Test Event",
            type="Sports",
            date="2026-10-04",
            location="Test Venue",
            description="pytest",
        )
    )
    return ev.id


def _patch_common(monkeypatch, files, download_map=None, fail_folder=False, fail_config=False):
    """Patch all Google + pipeline touchpoints so tests run fully offline."""
    monkeypatch.setattr(drive_service, "get_drive_service", lambda: object())
    if fail_config:
        def _raise_cfg():
            raise DriveConfigError("Google Drive is not configured on the server.")
        monkeypatch.setattr(drive_service, "get_drive_service", _raise_cfg)

    def _meta(service, folder_id):
        if fail_folder:
            raise DriveAccessError("Access denied. Share the folder with the service account.")
        return {"id": folder_id, "name": "folder"}

    monkeypatch.setattr(drive_service, "get_folder_metadata", _meta)
    monkeypatch.setattr(
        drive_service, "iter_folder_files", lambda service, folder_id, max_files=500: iter(files)
    )

    def _download(service, file_id, max_attempts=3):
        data = (download_map or {}).get(file_id, _valid_png_bytes())
        if isinstance(data, Exception):
            raise data
        return data

    monkeypatch.setattr(drive_service, "download_file", _download)

    processed = []

    def _fake_pipeline(event_id, file_bytes, filename, *args, **kwargs):
        if file_bytes == b"CORRUPT":
            raise ValueError("corrupt image data")
        processed.append(filename)
        return object()

    monkeypatch.setattr(import_service, "process_photo_bytes", _fake_pipeline)
    return processed


def _run(job_id: str):
    asyncio.run(import_service.run_job(job_id))
    return import_service.get_job(job_id)


# ---------------------------------------------------------------------------
# URL parsing
# ---------------------------------------------------------------------------

def test_extract_folder_id_variants():
    assert (
        drive_service.extract_folder_id("https://drive.google.com/drive/folders/1AbCdEfGhIjK")
        == "1AbCdEfGhIjK"
    )
    assert (
        drive_service.extract_folder_id("https://drive.google.com/drive/u/1/folders/XYZ_1234567890?usp=sharing")
        == "XYZ_1234567890"
    )
    assert drive_service.extract_folder_id("1AbCdEfGhIjK") == "1AbCdEfGhIjK"
    with pytest.raises(drive_service.DriveURLError):
        drive_service.extract_folder_id("https://example.com/not-drive")
    with pytest.raises(drive_service.DriveURLError):
        drive_service.extract_folder_id("")


# ---------------------------------------------------------------------------
# Import job behavior (mocked Google API + pipeline)
# ---------------------------------------------------------------------------

def test_mixed_import_success_corrupt_unsupported_oversized(monkeypatch):
    event_id = _make_event()
    files = [
        {"id": "f1", "name": "a.png", "mimeType": "image/png", "size": "100"},
        {"id": "f2", "name": "b.jpg", "mimeType": "image/jpeg", "size": "100"},
        {"id": "f3", "name": "broken.png", "mimeType": "image/png", "size": "100"},
        {"id": "f4", "name": "notes.txt", "mimeType": "text/plain", "size": "10"},
        {"id": "f5", "name": "huge.jpg", "mimeType": "image/jpeg", "size": str(50 * 1024 * 1024)},
    ]
    processed = _patch_common(
        monkeypatch, files, download_map={"f3": b"CORRUPT", "f1": _valid_png_bytes(), "f2": _valid_png_bytes()}
    )

    job = import_service.create_job(event_id, "https://drive.google.com/drive/folders/1AbCdEfGhIjK")
    job = _run(job["id"])

    assert job["status"] == "completed_with_errors"
    assert job["total"] == 5
    assert job["processed"] == 5
    assert job["successful"] == 2
    assert job["skipped"] == 1  # notes.txt
    assert job["failed"] == 2  # broken.png + huge.jpg
    assert job["remaining"] == 0
    assert job["percentage"] == 100.0
    assert processed == ["a.png", "b.jpg"]
    assert any("Unsupported" in e["error"] for e in job["errors"])
    assert any("corrupt" in e["error"] for e in job["errors"])
    assert any("limit" in e["error"] for e in job["errors"])


def test_duplicate_import_is_skipped(monkeypatch):
    event_id = _make_event()
    files = [
        {"id": "dup1", "name": "a.png", "mimeType": "image/png", "size": "10"},
        {"id": "dup2", "name": "b.png", "mimeType": "image/png", "size": "10"},
    ]
    _patch_common(monkeypatch, files)

    job1 = _run(import_service.create_job(event_id, "1AbCdEfGhIjK")["id"])
    assert job1["successful"] == 2
    assert job1["skipped"] == 0

    # Second run of the same folder must NOT re-import
    job2 = _run(import_service.create_job(event_id, "1AbCdEfGhIjK")["id"])
    assert job2["successful"] == 0
    assert job2["skipped"] == 2
    assert db.is_drive_file_imported(event_id, "dup1")
    assert db.is_drive_file_imported(event_id, "dup2")


def test_malformed_url_fails_job(monkeypatch):
    event_id = _make_event()
    _patch_common(monkeypatch, [])
    job = _run(import_service.create_job(event_id, "https://example.com/nope")["id"])
    assert job["status"] == "failed"
    assert "folder ID" in job["message"]


def test_inaccessible_folder(monkeypatch):
    event_id = _make_event()
    _patch_common(monkeypatch, [], fail_folder=True)
    job = _run(import_service.create_job(event_id, "1AbCdEfGhIjK")["id"])
    assert job["status"] == "failed"
    assert "Access denied" in job["message"]


def test_missing_google_configuration(monkeypatch):
    event_id = _make_event()
    _patch_common(monkeypatch, [], fail_config=True)
    job = _run(import_service.create_job(event_id, "1AbCdEfGhIjK")["id"])
    assert job["status"] == "failed"
    assert "not configured" in job["message"]


def test_empty_folder(monkeypatch):
    event_id = _make_event()
    _patch_common(monkeypatch, [])
    job = _run(import_service.create_job(event_id, "1AbCdEfGhIjK")["id"])
    assert job["status"] == "completed"
    assert job["total"] == 0
    assert "empty" in job["message"].lower()


def test_unsupported_files_only(monkeypatch):
    event_id = _make_event()
    files = [
        {"id": "t1", "name": "a.txt", "mimeType": "text/plain", "size": "5"},
        {"id": "t2", "name": "b.pdf", "mimeType": "application/pdf", "size": "5"},
    ]
    _patch_common(monkeypatch, files)
    job = _run(import_service.create_job(event_id, "1AbCdEfGhIjK")["id"])
    assert job["successful"] == 0
    assert job["skipped"] == 2
    assert job["failed"] == 0


# ---------------------------------------------------------------------------
# HTTP API behavior
# ---------------------------------------------------------------------------

def test_route_rejects_malformed_url():
    events = client.get("/api/events").json()
    event_id = events[0]["id"]
    res = client.post(
        f"/api/events/{event_id}/imports/google-drive",
        json={"folder_url": "https://example.com/nope"},
    )
    assert res.status_code == 400


def test_route_rejects_unknown_event():
    res = client.post(
        "/api/events/does-not-exist/imports/google-drive",
        json={"folder_url": "https://drive.google.com/drive/folders/1AbCdEfGhIjK"},
    )
    assert res.status_code == 404


def test_route_starts_job_and_reports_status(monkeypatch):
    async def _noop(job_id):
        return None

    monkeypatch.setattr(import_service, "run_job", _noop)
    events = client.get("/api/events").json()
    event_id = events[0]["id"]

    res = client.post(
        f"/api/events/{event_id}/imports/google-drive",
        json={"folder_url": "https://drive.google.com/drive/folders/1AbCdEfGhIjK?usp=sharing"},
    )
    assert res.status_code == 202
    job = res.json()
    assert job["status"] == "queued"
    assert job["event_id"] == event_id

    res2 = client.get(f"/api/imports/{job['id']}")
    assert res2.status_code == 200
    assert res2.json()["id"] == job["id"]

    res3 = client.post(f"/api/imports/{job['id']}/cancel")
    assert res3.status_code == 200

    res4 = client.get("/api/imports/no-such-job")
    assert res4.status_code == 404
