"""
Background Google Drive import job runner.

Processes photos strictly one at a time:
    Drive file -> download -> face detect -> Cloudinary -> DB index -> next

Job state is kept in memory (Render-compatible). Active jobs are LOST if
the Render process restarts or redeploys; the already-imported photos and
their duplicate IDs in the in-memory DB are equally in-memory, so a restart
resets everything consistently.
"""
import asyncio
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.config import settings
from app.database import db
from app.services import drive_service
from app.services.drive_service import DriveAccessError, DriveConfigError, DriveURLError
from app.services.photo_pipeline import process_photo_bytes

JOBS: Dict[str, Dict[str, Any]] = {}
_CANCEL_FLAGS: Dict[str, bool] = {}

IMAGE_MIME_PREFIX = "image/"


def _now() -> str:
    return datetime.utcnow().isoformat()


def create_job(event_id: str, folder_url: str) -> Dict[str, Any]:
    job_id = f"import_{uuid.uuid4().hex[:8]}"
    job = {
        "id": job_id,
        "event_id": event_id,
        "folder_url": folder_url,
        "status": "queued",  # queued | running | completed | completed_with_errors | failed | cancelled
        "total": 0,
        "processed": 0,
        "successful": 0,
        "skipped": 0,
        "failed": 0,
        "remaining": 0,
        "percentage": 0.0,
        "current_filename": None,
        "message": "Import queued.",
        "errors": [],
        "created_at": _now(),
        "finished_at": None,
    }
    JOBS[job_id] = job
    _CANCEL_FLAGS[job_id] = False
    return job


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    return JOBS.get(job_id)


def cancel_job(job_id: str) -> bool:
    if job_id in _CANCEL_FLAGS:
        _CANCEL_FLAGS[job_id] = True
        return True
    return False


def _refresh_progress(job: Dict[str, Any]):
    total = job["total"]
    job["remaining"] = max(total - job["processed"], 0)
    job["percentage"] = round((job["processed"] / total) * 100, 1) if total > 0 else (100.0 if job["status"] in ("completed", "completed_with_errors") else 0.0)


def _record_error(job: Dict[str, Any], filename: Optional[str], message: str):
    job["errors"].append({"file": filename or "", "error": message[:500]})


async def run_job(job_id: str):
    job = JOBS.get(job_id)
    if job is None:
        return

    job["status"] = "running"
    job["message"] = "Connecting to Google Drive..."
    event_id = job["event_id"]

    # 1. Parse folder URL
    try:
        folder_id = drive_service.extract_folder_id(job["folder_url"])
    except DriveURLError as e:
        job["status"] = "failed"
        job["message"] = str(e)
        _record_error(job, None, str(e))
        job["finished_at"] = _now()
        return

    # 2. Build authenticated client
    try:
        service = drive_service.get_drive_service()
    except DriveConfigError as e:
        job["status"] = "failed"
        job["message"] = str(e)
        _record_error(job, None, str(e))
        job["finished_at"] = _now()
        return

    # 3. Validate folder access
    try:
        await asyncio.to_thread(drive_service.get_folder_metadata, service, folder_id)
    except DriveAccessError as e:
        job["status"] = "failed"
        job["message"] = str(e)
        _record_error(job, None, str(e))
        job["finished_at"] = _now()
        return

    # 4. List files (one page at a time; not the whole folder in memory)
    try:
        files: List[Dict[str, Any]] = []
        max_files = int(getattr(settings, "MAX_IMPORT_FILES", 500) or 500)
        for f in drive_service.iter_folder_files(service, folder_id, max_files=max_files):
            files.append(f)
    except DriveAccessError as e:
        job["status"] = "failed"
        job["message"] = str(e)
        _record_error(job, None, str(e))
        job["finished_at"] = _now()
        return

    job["total"] = len(files)
    job["remaining"] = job["total"]
    job["message"] = f"Found {job['total']} file(s). Starting import..."

    if job["total"] == 0:
        job["status"] = "completed"
        job["message"] = "Folder is empty or contains no supported files."
        job["percentage"] = 100.0
        job["finished_at"] = _now()
        return

    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    # 5. Process strictly one file at a time
    for f in files:
        if _CANCEL_FLAGS.get(job_id):
            job["status"] = "cancelled"
            job["message"] = f"Import cancelled after {job['processed']} file(s)."
            _refresh_progress(job)
            job["finished_at"] = _now()
            return

        name = f.get("name", "unknown")
        mime = f.get("mimeType", "")
        job["current_filename"] = name

        # Unsupported (non-image) files are skipped, not fatal
        if not mime.startswith(IMAGE_MIME_PREFIX):
            job["skipped"] += 1
            job["processed"] += 1
            _record_error(job, name, f"Unsupported file type '{mime}' - skipped.")
            _refresh_progress(job)
            continue

        # Duplicate by Google Drive file ID
        if db.is_drive_file_imported(event_id, f.get("id", "")):
            job["skipped"] += 1
            job["processed"] += 1
            _record_error(job, name, "Already imported (duplicate Drive file) - skipped.")
            _refresh_progress(job)
            continue

        # Oversized files are rejected without stopping the import
        try:
            size = int(f.get("size") or 0)
        except (TypeError, ValueError):
            size = 0
        if size > max_bytes:
            job["failed"] += 1
            job["processed"] += 1
            _record_error(job, name, f"File exceeds {settings.MAX_UPLOAD_SIZE_MB}MB limit - skipped.")
            _refresh_progress(job)
            continue

        try:
            data = await asyncio.to_thread(drive_service.download_file, service, f["id"])
            if len(data) == 0:
                raise ValueError("Downloaded file is empty")
            if len(data) > max_bytes:
                raise ValueError(f"File exceeds {settings.MAX_UPLOAD_SIZE_MB}MB limit")

            await asyncio.to_thread(
                process_photo_bytes,
                event_id,
                data,
                name,
                "12:00 PM",
                "Event Venue",
                "Staff Photographer",
                "Sony A7 IV • 85mm f/1.4",
                None,
            )

            db.mark_drive_file_imported(event_id, f["id"])
            job["successful"] += 1
        except Exception as e:
            job["failed"] += 1
            _record_error(job, name, str(e))
        finally:
            # Release temporary resources before moving to the next file
            data = None

        job["processed"] += 1
        _refresh_progress(job)

    if job["failed"] > 0 and job["successful"] == 0 and job["skipped"] == 0:
        job["status"] = "failed"
        job["message"] = f"Import failed for all {job['failed']} file(s)."
    elif job["failed"] > 0:
        job["status"] = "completed_with_errors"
        job["message"] = (
            f"Import finished: {job['successful']} imported, "
            f"{job['skipped']} skipped, {job['failed']} failed."
        )
    else:
        job["status"] = "completed"
        job["message"] = (
            f"Import finished: {job['successful']} imported, {job['skipped']} skipped."
        )
    job["current_filename"] = None
    _refresh_progress(job)
    job["finished_at"] = _now()
