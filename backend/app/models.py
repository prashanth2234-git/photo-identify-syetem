from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class Photo(BaseModel):
    id: str
    event_id: str
    original_url: str
    cloudinary_public_id: str = ""
    thumbnail_url: str
    watermarked_url: str
    captured_time: str
    location: str
    photographer: str
    camera_meta: str = "Sony A7 IV • 85mm f/1.4"
    bib_numbers: List[str] = []
    faces_detected: int = 0
    width: int = 1920
    height: int = 1080
    likes: int = 0

class Event(BaseModel):
    id: str
    title: str
    type: str  # Sports, Wedding, College, Conference, Concert, Corporate, Other
    date: str
    location: str
    description: str
    cover_url: str
    total_photos: int = 0
    views: int = 0
    searches: int = 0
    photographer_name: str = "Professional Event Studio"
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

class SearchResult(BaseModel):
    photo: Photo
    confidence_score: float  # e.g., 0.97
    match_type: str  # "face" or "bib"
    detected_bib: Optional[str] = None

class SearchResponse(BaseModel):
    event_id: str
    event_title: str
    query_type: str  # "selfie" or "bib"
    total_matches: int
    results: List[SearchResult]
    processing_time_ms: float
    message: str

class CreateEventRequest(BaseModel):
    title: str
    type: str
    date: str
    location: str
    description: str
    cover_url: Optional[str] = None
    photographer_name: Optional[str] = "EventSnap Studio"

class PhotographerStats(BaseModel):
    total_events: int
    total_photos: int
    total_searches: int
    total_views: int
    conversion_rate: float
    active_cloud: str
    cloud_status: str

class DemoPersona(BaseModel):
    id: str
    name: str
    event_id: str
    event_name: str
    role_description: str
    selfie_url: str
    bib_number: Optional[str] = None

class DriveImportRequest(BaseModel):
    folder_url: str

class ImportJob(BaseModel):
    id: str
    event_id: str
    folder_url: str
    status: str
    total: int = 0
    processed: int = 0
    successful: int = 0
    skipped: int = 0
    failed: int = 0
    remaining: int = 0
    percentage: float = 0.0
    current_filename: Optional[str] = None
    message: str = ""
    errors: List[dict] = []
    created_at: str = ""
    finished_at: Optional[str] = None
