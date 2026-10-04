import asyncio
import io
from types import SimpleNamespace

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


def _patch_common(monkeypatch, files, download_map=None, fail_folder=False, fail_config=False, use_real_pipeline=False):
    """Patch all Google + pipeline touchpoints so tests run fully offline."""
    download_calls = []
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
        download_calls.append(file_id)
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
        return SimpleNamespace(faces_detected=0)

    if use_real_pipeline:
        pass  # exercise the real face detection + indexing path
    else:
        monkeypatch.setattr(import_service, "process_photo_bytes", _fake_pipeline)
    return SimpleNamespace(processed=processed, download_calls=download_calls)


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
        {"id": "f5", "name": "huge.jpg", "mimeType": "image/jpeg", "size": str(60 * 1024 * 1024)},
    ]
    ctx = _patch_common(
        monkeypatch, files, download_map={"f3": b"CORRUPT", "f1": _valid_png_bytes(), "f2": _valid_png_bytes()}
    )
    processed = ctx.processed

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
    assert any("50 MB" in e["error"] for e in job["errors"])
    # The 60 MB file must be rejected from Drive metadata BEFORE downloading
    assert "f5" not in ctx.download_calls
    # Counters must reflect that "successful" does NOT imply faces were found
    assert job["with_faces"] == 0
    assert job["no_faces"] == 2  # fake pipeline reports zero faces


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


# ---------------------------------------------------------------------------
# Folder listing: non-recursive + image-only + MAX_IMPORT_FILES
# ---------------------------------------------------------------------------

class _FakeReq:
    def __init__(self, payload):
        self.payload = payload

    def execute(self):
        return self.payload


class _FakeFiles:
    def __init__(self, pages):
        self.pages = pages
        self.q_values = []

    def list(self, **kwargs):
        self.q_values.append(kwargs.get("q", ""))
        payload = self.pages[min(len(self.q_values) - 1, len(self.pages) - 1)]
        return _FakeReq(payload)


class _FakeService:
    def __init__(self, pages):
        self._files = _FakeFiles(pages)

    def files(self):
        return self._files


def test_listing_is_non_recursive_and_images_only():
    page = {
        "files": [
            {"id": "i1", "name": "a.jpg", "mimeType": "image/jpeg", "size": "10"},
            {"id": "i2", "name": "b.png", "mimeType": "image/png", "size": "10"},
            {"id": "sub", "name": "Subfolder", "mimeType": "application/vnd.google-apps.folder"},
        ],
        "nextPageToken": None,
    }
    svc = _FakeService([page])
    out = list(drive_service.iter_folder_files(svc, "folder123", max_files=1000))

    # Only direct image children are yielded; the subfolder is never recursed into
    assert [f["id"] for f in out] == ["i1", "i2"]
    # Exactly ONE list call (no second call for the subfolder) and image filter in query
    assert len(svc._files.q_values) == 1
    assert "'folder123' in parents" in svc._files.q_values[0]
    assert "mimeType contains 'image/'" in svc._files.q_values[0]


def test_listing_respects_max_import_files_cap():
    page = {
        "files": [
            {"id": f"i{i}", "name": f"{i}.jpg", "mimeType": "image/jpeg", "size": "10"}
            for i in range(5)
        ],
        "nextPageToken": None,
    }
    svc = _FakeService([page])
    out = list(drive_service.iter_folder_files(svc, "folder123", max_files=3))
    assert len(out) == 3


# ---------------------------------------------------------------------------
# Real pipeline verification: Drive image -> faces -> searchable index
# ---------------------------------------------------------------------------

_FACE_SAMPLE = __import__("os").path.join(
    __import__("os").path.dirname(__import__("os").path.abspath(__file__)),
    "test_fixtures",
    "face_sample.jpg",
)


def test_drive_import_indexes_real_face_and_is_searchable(monkeypatch):
    import os

    if not os.path.exists(_FACE_SAMPLE):
        pytest.skip("face_sample.jpg fixture missing")

    event_id = _make_event()
    data = open(_FACE_SAMPLE, "rb").read()
    files = [{"id": "real1", "name": "face_sample.jpg", "mimeType": "image/jpeg", "size": str(len(data))}]
    _patch_common(monkeypatch, files, download_map={"real1": data}, use_real_pipeline=True)
    from app.services import cloudinary_service as cs_mod

    monkeypatch.setattr(
        cs_mod.cloudinary_service,
        "upload_photo",
        lambda fb, eid, fname: {
            "public_id": f"eventsnap/events/{eid}/x",
            "original_url": "https://example.com/orig",
            "thumbnail_url": "https://example.com/t",
            "watermarked_url": "https://example.com/w",
        },
    )

    job = _run(import_service.create_job(event_id, "1AbCdEfGhIjK")["id"])
    assert job["status"] == "completed"
    assert job["successful"] == 1
    assert job["with_faces"] == 1
    assert job["no_faces"] == 0

    indexed = db.get_event_faces(event_id)
    assert len(indexed) >= 1, "Drive-imported photo did not index any faces"

    # Find My Photos path: same image as selfie must match via the shared index
    from app.services.face_service import face_engine

    vec, _ = face_engine.validate_and_embed_selfie(data)
    matches = face_engine.match_selfie(vec, indexed, threshold=0.50)
    assert len(matches) >= 1
    assert matches[0]["confidence"] >= 0.50


def test_drive_import_no_face_image_is_reported_without_faces(monkeypatch):
    event_id = _make_event()
    no_face_png = _valid_png_bytes()  # solid color square: no person/face
    files = [{"id": "nf1", "name": "solid.png", "mimeType": "image/png", "size": str(len(no_face_png))}]
    _patch_common(monkeypatch, files, download_map={"nf1": no_face_png}, use_real_pipeline=True)
    from app.services import cloudinary_service as cs_mod

    monkeypatch.setattr(
        cs_mod.cloudinary_service,
        "upload_photo",
        lambda fb, eid, fname: {
            "public_id": f"eventsnap/events/{eid}/x",
            "original_url": "https://example.com/orig",
            "thumbnail_url": "https://example.com/t",
            "watermarked_url": "https://example.com/w",
        },
    )

    job = _run(import_service.create_job(event_id, "1AbCdEfGhIjK")["id"])
    assert job["successful"] == 1
    assert job["with_faces"] == 0
    assert job["no_faces"] == 1
    assert any("no faces detected" in e["error"] for e in job["errors"])
    assert len(db.get_event_faces(event_id)) == 0


# ---------------------------------------------------------------------------
# HEIF/HEIC/HIF decoding support
# ---------------------------------------------------------------------------


def _heif_bytes(pil_image) -> bytes:
    import os
    if not os.path.exists(_FACE_SAMPLE):
        pytest.skip("face_sample.jpg fixture missing")
    from pillow_heif import register_heif_opener

    register_heif_opener()
    buf = io.BytesIO()
    pil_image.convert("RGB").save(buf, format="HEIF")
    return buf.getvalue()


def test_jpg_and_png_bytes_pass_through_unchanged():
    from app.services.image_decoder import image_bytes_for_opencv

    jpg = open(_FACE_SAMPLE, "rb").read()
    out, converted = image_bytes_for_opencv(jpg)
    assert converted is False
    assert out == jpg  # original bytes, no forced Pillow conversion

    png = _valid_png_bytes()
    out2, converted2 = image_bytes_for_opencv(png)
    assert converted2 is False
    assert out2 == png


def test_heif_decodes_and_face_is_indexed_via_same_pipeline(monkeypatch):
    import os

    if not os.path.exists(_FACE_SAMPLE):
        pytest.skip("face_sample.jpg fixture missing")

    event_id = _make_event()
    heif_data = _heif_bytes(Image.open(_FACE_SAMPLE))
    files = [{"id": "heif1", "name": "DSC06692.HIF", "mimeType": "image/heif", "size": str(len(heif_data))}]
    _patch_common(monkeypatch, files, download_map={"heif1": heif_data}, use_real_pipeline=True)
    from app.services import cloudinary_service as cs_mod

    monkeypatch.setattr(
        cs_mod.cloudinary_service,
        "upload_photo",
        lambda fb, eid, fname: {
            "public_id": f"eventsnap/events/{eid}/x",
            "original_url": "https://example.com/orig",
            "thumbnail_url": "https://example.com/t",
            "watermarked_url": "https://example.com/w",
        },
    )

    job = _run(import_service.create_job(event_id, "1AbCdEfGhIjK")["id"])
    assert job["successful"] == 1, job["errors"]
    assert job["with_faces"] == 1
    assert job["no_faces"] == 0

    indexed = db.get_event_faces(event_id)
    assert len(indexed) >= 1

    from app.services.face_service import face_engine

    vec, _ = face_engine.validate_and_embed_selfie(open(_FACE_SAMPLE, "rb").read())
    assert len(face_engine.match_selfie(vec, indexed, threshold=0.50)) >= 1


def test_heif_without_face_reports_no_faces(monkeypatch):
    event_id = _make_event()
    heif_no_face = _heif_bytes(Image.new("RGB", (64, 64), (20, 90, 140)))
    files = [{"id": "heif2", "name": "frame.heic", "mimeType": "image/heic", "size": str(len(heif_no_face))}]
    _patch_common(monkeypatch, files, download_map={"heif2": heif_no_face}, use_real_pipeline=True)
    from app.services import cloudinary_service as cs_mod

    monkeypatch.setattr(
        cs_mod.cloudinary_service,
        "upload_photo",
        lambda fb, eid, fname: {
            "public_id": f"eventsnap/events/{eid}/x",
            "original_url": "https://example.com/orig",
            "thumbnail_url": "https://example.com/t",
            "watermarked_url": "https://example.com/w",
        },
    )

    job = _run(import_service.create_job(event_id, "1AbCdEfGhIjK")["id"])
    assert job["successful"] == 1
    assert job["with_faces"] == 0
    assert job["no_faces"] == 1
    assert any("no faces detected" in e["error"] for e in job["errors"])


def test_corrupt_heif_bytes_are_handled_gracefully(monkeypatch):
    event_id = _make_event()
    corrupt = b"\x00\x00\x00\x18ftypheic" + b"\xff" * 64  # plausible HEIF header, garbage payload
    files = [{"id": "heif3", "name": "broken.heif", "mimeType": "image/heif", "size": str(len(corrupt))}]
    _patch_common(monkeypatch, files, download_map={"heif3": corrupt}, use_real_pipeline=True)

    # Stub Cloudinary upload so the test isolates decode-failure classification only
    from app.services import cloudinary_service as cs_mod

    monkeypatch.setattr(
        cs_mod.cloudinary_service,
        "upload_photo",
        lambda file_bytes, event_id, filename: {
            "public_id": f"eventsnap/events/{event_id}/x",
            "original_url": "https://example.com/orig",
            "thumbnail_url": "https://example.com/t",
            "watermarked_url": "https://example.com/w",
        },
    )

    job = _run(import_service.create_job(event_id, "1AbCdEfGhIjK")["id"])
    # Decode failure must NOT be classified as a face-detection success
    assert job["successful"] == 0
    assert job["failed"] == 1
    assert any("HEIF" in e["error"] for e in job["errors"])
    assert len(db.get_event_faces(event_id)) == 0


def test_heif_original_bytes_go_to_cloudinary(monkeypatch):
    import os

    if not os.path.exists(_FACE_SAMPLE):
        pytest.skip("face_sample.jpg fixture missing")

    event_id = _make_event()
    heif_data = _heif_bytes(Image.open(_FACE_SAMPLE))
    captured = {}

    from app.services import cloudinary_service as cs_mod

    def _capture_upload(file_bytes, event_id, filename):
        captured["bytes"] = file_bytes
        return {
            "public_id": f"eventsnap/events/{event_id}/x",
            "original_url": "https://example.com/orig",
            "thumbnail_url": "https://example.com/t",
            "watermarked_url": "https://example.com/w",
        }

    monkeypatch.setattr(cs_mod.cloudinary_service, "upload_photo", _capture_upload)
    files = [{"id": "heif4", "name": "DSC06692.HIF", "mimeType": "image/heif", "size": str(len(heif_data))}]
    _patch_common(monkeypatch, files, download_map={"heif4": heif_data}, use_real_pipeline=True)

    job = _run(import_service.create_job(event_id, "1AbCdEfGhIjK")["id"])
    assert job["successful"] == 1, job["errors"]
    assert captured["bytes"] is heif_data or captured["bytes"] == heif_data
