import asyncio
from fastapi import APIRouter, HTTPException

from app.database import db
from app.models import DriveImportRequest, ImportJob
from app.services import import_service
from app.services.drive_service import extract_folder_id, DriveURLError

router = APIRouter(prefix="/api", tags=["imports"])


@router.post("/events/{event_id}/imports/google-drive", response_model=ImportJob, status_code=202)
async def start_google_drive_import(event_id: str, req: DriveImportRequest):
    event = db.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    if not req.folder_url or not req.folder_url.strip():
        raise HTTPException(status_code=400, detail="folder_url is required")

    try:
        extract_folder_id(req.folder_url)
    except DriveURLError as e:
        raise HTTPException(status_code=400, detail=str(e))

    job = import_service.create_job(event_id, req.folder_url.strip())
    # Fire-and-forget background job; the POST returns immediately.
    asyncio.create_task(import_service.run_job(job["id"]))
    return job


@router.get("/imports/{job_id}", response_model=ImportJob)
def get_import_status(job_id: str):
    job = import_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Import job not found")
    return job


@router.post("/imports/{job_id}/cancel", response_model=ImportJob)
def cancel_import(job_id: str):
    job = import_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Import job not found")
    if job["status"] in ("completed", "completed_with_errors", "failed", "cancelled"):
        return job
    import_service.cancel_job(job_id)
    job["message"] = "Cancellation requested..."
    return job
