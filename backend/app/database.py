import uuid
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
from app.models import Event, Photo, SearchResult, CreateEventRequest, PhotographerStats, DemoPersona
from app.services.face_service import face_engine
from app.services.cloudinary_service import cloudinary_service

class InMemoryDB:
    def __init__(self):
        self.events: Dict[str, Event] = {}
        self.photos: Dict[str, Photo] = {}
        self.event_photos: Dict[str, List[str]] = {}
        # Rich indexed faces: List of Dicts with photo_id, event_id, cloudinary_public_id, bbox, landmarks, embedding, persona_tag
        self.face_index: List[Dict[str, Any]] = []
        # Legacy compatibility tuple list: (photo_id, embedding, persona_tag)
        self.face_embeddings: List[Tuple[str, np.ndarray, Optional[str]]] = []
        self.demo_personas: List[DemoPersona] = []
        self.search_sessions: List[Dict[str, Any]] = []
        # Google Drive duplicate tracking: event_id -> set of imported Drive file IDs
        self.drive_file_ids: Dict[str, set] = {}

    def get_all_events(self) -> List[Event]:
        return list(self.events.values())

    def get_event(self, event_id: str) -> Optional[Event]:
        return self.events.get(event_id)

    def create_event(self, req: CreateEventRequest) -> Event:
        event_id = str(uuid.uuid4())[:8]
        cover_url = req.cover_url or "https://images.unsplash.com/photo-1540575467063-178a50c2df87?w=1200&auto=format&fit=crop&q=80"
        event = Event(
            id=event_id,
            title=req.title,
            type=req.type,
            date=req.date,
            location=req.location,
            description=req.description,
            cover_url=cover_url,
            total_photos=0,
            views=0,
            searches=0,
            photographer_name=req.photographer_name or "EventSnap Studio"
        )
        self.events[event_id] = event
        self.event_photos[event_id] = []
        return event

    def get_photos_for_event(self, event_id: str) -> List[Photo]:
        photo_ids = self.event_photos.get(event_id, [])
        return [self.photos[pid] for pid in photo_ids if pid in self.photos]

    def get_photo(self, photo_id: str) -> Optional[Photo]:
        return self.photos.get(photo_id)

    def index_faces(
        self,
        photo_id: str,
        event_id: str,
        faces: List[Dict[str, Any]],
        cloudinary_public_id: Optional[str] = None,
        persona_tag: Optional[str] = None
    ):
        """
        Indexes all faces detected in a photo.
        Enforces linkage to event_id, photo_id, and Cloudinary public_id.
        """
        for face in faces:
            entry = {
                "face_id": f"face_{str(uuid.uuid4())[:8]}",
                "photo_id": photo_id,
                "event_id": event_id,
                "cloudinary_public_id": cloudinary_public_id,
                "bbox": face.get("bbox", [0, 0, 0, 0]),
                "landmarks": face.get("landmarks", []),
                "score": face.get("score", 1.0),
                "embedding": face["embedding"],
                "persona_tag": persona_tag
            }
            self.face_index.append(entry)
            self.face_embeddings.append((photo_id, face["embedding"], persona_tag))

    def get_event_faces(self, event_id: str) -> List[Dict[str, Any]]:
        """
        Returns all face index entries strictly belonging to the given event_id (Event Isolation).
        """
        return [f for f in self.face_index if f["event_id"] == event_id]

    def add_photo(
        self,
        event_id: str,
        original_url: str,
        captured_time: str,
        location: str,
        photographer: str,
        camera_meta: str = "Sony A7 IV • 85mm f/1.4",
        bib_numbers: Optional[List[str]] = None,
        persona_tag: Optional[str] = None,
        custom_embedding: Optional[np.ndarray] = None,
        detected_faces: Optional[List[Dict[str, Any]]] = None,
        cloudinary_public_id: Optional[str] = None,
        thumbnail_url: Optional[str] = None,
        watermarked_url: Optional[str] = None
    ) -> Photo:
        photo_id = f"ph_{str(uuid.uuid4())[:8]}"
        bib_numbers = bib_numbers or []
        
        cid = cloudinary_public_id or f"eventsnap/{event_id}/{photo_id}"
        thumb_url = thumbnail_url or cloudinary_service.generate_face_crop_url(cid if cloudinary_public_id else original_url)
        wmark_url = watermarked_url or cloudinary_service.generate_watermarked_url(cid if cloudinary_public_id else original_url)
        optimized_url = cloudinary_service.generate_optimized_url(cid if cloudinary_public_id else original_url)

        num_faces = len(detected_faces) if detected_faces is not None else (1 if (custom_embedding is not None or persona_tag) else 0)

        photo = Photo(
            id=photo_id,
            event_id=event_id,
            original_url=original_url or optimized_url,
            cloudinary_public_id=cid,
            thumbnail_url=thumb_url,
            watermarked_url=wmark_url,
            captured_time=captured_time,
            location=location,
            photographer=photographer,
            camera_meta=camera_meta,
            bib_numbers=bib_numbers,
            faces_detected=num_faces,
            width=1920,
            height=1080
        )
        self.photos[photo_id] = photo
        if event_id not in self.event_photos:
            self.event_photos[event_id] = []
        self.event_photos[event_id].append(photo_id)
        
        # Update event photo count
        if event_id in self.events:
            self.events[event_id].total_photos += 1

        # Index faces
        if detected_faces and len(detected_faces) > 0:
            self.index_faces(photo_id, event_id, detected_faces, cid, persona_tag)
        elif custom_embedding is not None:
            self.index_faces(photo_id, event_id, [{"embedding": custom_embedding}], cid, persona_tag)
        elif persona_tag and face_engine.get_persona_embedding(persona_tag) is not None:
            p_vec = face_engine.get_persona_embedding(persona_tag)
            self.index_faces(photo_id, event_id, [{"embedding": p_vec}], cid, persona_tag)

        return photo

    def clear_event_photos(self, event_id: str) -> int:
        """Safely clears photos and indexed faces for a specific event."""
        photo_ids = self.event_photos.get(event_id, [])
        count = len(photo_ids)
        for pid in photo_ids:
            if pid in self.photos:
                del self.photos[pid]
        self.event_photos[event_id] = []
        self.face_index = [f for f in self.face_index if f["event_id"] != event_id]
        self.face_embeddings = [
            (pid, vec, ptag) for pid, vec, ptag in self.face_embeddings
            if pid not in photo_ids
        ]
        if event_id in self.events:
            self.events[event_id].total_photos = 0
        return count

    def is_drive_file_imported(self, event_id: str, drive_file_id: str) -> bool:
        return drive_file_id in self.drive_file_ids.get(event_id, set())

    def mark_drive_file_imported(self, event_id: str, drive_file_id: str):
        if event_id not in self.drive_file_ids:
            self.drive_file_ids[event_id] = set()
        self.drive_file_ids[event_id].add(drive_file_id)

    def record_search(self, event_id: str, query_type: str, match_count: int):
        if event_id in self.events:
            self.events[event_id].searches += 1
        self.search_sessions.append({
            "session_id": str(uuid.uuid4()),
            "event_id": event_id,
            "query_type": query_type,
            "match_count": match_count
        })

    def record_view(self, event_id: str):
        if event_id in self.events:
            self.events[event_id].views += 1

    def clear_search_data(self) -> int:
        """Privacy compliance: wipes user search history & transient sessions"""
        cleared_count = len(self.search_sessions)
        self.search_sessions.clear()
        return cleared_count

    def get_photographer_stats(self) -> PhotographerStats:
        total_photos = sum(e.total_photos for e in self.events.values())
        total_searches = sum(e.searches for e in self.events.values())
        total_views = sum(e.views for e in self.events.values())
        conversion = round((total_views / max(total_searches, 1)) * 100, 1)
        
        is_live = cloudinary_service.is_live_account_configured()
        cloud_name = cloudinary_service.cloud_name or "demo"
        
        return PhotographerStats(
            total_events=len(self.events),
            total_photos=total_photos,
            total_searches=total_searches,
            total_views=total_views,
            conversion_rate=min(conversion, 94.5),
            active_cloud=cloud_name,
            cloud_status="Connected (Live Cloudinary API)" if is_live else "Connected (Cloudinary Dynamic Media Engine)"
        )

db = InMemoryDB()
