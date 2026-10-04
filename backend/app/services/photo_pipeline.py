"""
Shared photo-processing pipeline.

This mirrors EXACTLY the logic that the manual upload endpoint
(POST /api/events/{event_id}/photos) has always executed:

    1. Detect ALL faces with the YuNet + SFace engine (face_service.face_engine)
    2. Upload the media to Cloudinary (cloudinary_service.upload_photo)
    3. Parse bib numbers (ocr_service.bib_ocr_engine)
    4. Persist to the in-memory DB with detected faces indexed (db.add_photo)

Both the manual upload route and the Google Drive importer route feed
through this single function so behavior is identical regardless of the
source of the bytes.
"""
from typing import Optional

from app.database import db
from app.models import Photo
from app.services.cloudinary_service import cloudinary_service
from app.services.face_service import face_engine
from app.services.ocr_service import bib_ocr_engine
from app.services.image_decoder import image_bytes_for_opencv, ImageDecodeError


def process_photo_bytes(
    event_id: str,
    file_bytes: bytes,
    filename: str,
    captured_time: str = "12:00 PM",
    location: str = "Event Venue",
    photographer: str = "Staff Photographer",
    camera_meta: str = "Sony A7 IV • 85mm f/1.4",
    bib_numbers_str: Optional[str] = None,
) -> Photo:
    if len(file_bytes) == 0:
        raise ValueError("Empty photo file provided")

    # 1. Detect ALL faces in the photo (handles multiple people)
    # JPEG/PNG pass through unchanged; HEIF/HEIC/HIF is converted to a
    # temporary CV-only JPEG so it uses the SAME YuNet/SFace pipeline.
    try:
        cv_bytes, _is_heif = image_bytes_for_opencv(file_bytes)
    except ImageDecodeError:
        # Keep legacy semantics: detection on raw bytes (will yield no faces),
        # import classification happens in import_service with clear messages.
        cv_bytes = file_bytes
    detected_faces = face_engine.detect_faces(cv_bytes)

    # 2. Upload media to Cloudinary
    upload_res = cloudinary_service.upload_photo(file_bytes, event_id, filename or "photo.jpg")

    # 3. Extract OCR bibs if provided
    bibs = []
    if bib_numbers_str:
        bibs = bib_ocr_engine.extract_bib_numbers(bib_numbers_str)

    # 4. Save to database with real Cloudinary identifiers and index ALL detected faces
    photo = db.add_photo(
        event_id=event_id,
        original_url=upload_res["original_url"],
        captured_time=captured_time,
        location=location,
        photographer=photographer,
        camera_meta=camera_meta,
        bib_numbers=bibs,
        detected_faces=detected_faces,
        cloudinary_public_id=upload_res.get("public_id"),
        thumbnail_url=upload_res.get("thumbnail_url"),
        watermarked_url=upload_res.get("watermarked_url"),
    )
    return photo
