import { Event, Photo, SearchResponse, DemoPersona, PhotographerStats, CreateEventPayload, ImportJob } from '../types';

const rawBase = import.meta.env.VITE_API_URL ? import.meta.env.VITE_API_URL.replace(/\/+$/, '') : '';
export const API_BASE = rawBase ? (rawBase.endsWith('/api') ? rawBase : `${rawBase}/api`) : '/api';

export const api = {
  async getEventFaceIndex(eventId: string): Promise<{ total_indexed_faces: number; total_photos: number }> {
    const res = await fetch(`${API_BASE}/events/${encodeURIComponent(eventId)}/face-index`);
    if (!res.ok) throw new Error('Failed to fetch face index');
    return res.json();
  },

  async getEvents(category?: string): Promise<Event[]> {
    const url = category && category !== 'All' ? `${API_BASE}/events?category=${encodeURIComponent(category)}` : `${API_BASE}/events`;
    const res = await fetch(url);
    if (!res.ok) throw new Error('Failed to fetch events');
    return res.json();
  },

  async getEventDetail(eventId: string): Promise<{ event: Event; photos: Photo[] }> {
    const res = await fetch(`${API_BASE}/events/${eventId}`);
    if (!res.ok) throw new Error('Failed to fetch event detail');
    return res.json();
  },

  async createEvent(payload: CreateEventPayload): Promise<Event> {
    const res = await fetch(`${API_BASE}/events`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!res.ok) throw new Error('Failed to create event');
    return res.json();
  },

  async getDemoPersonas(): Promise<DemoPersona[]> {
    const res = await fetch(`${API_BASE}/demo-personas`);
    if (!res.ok) throw new Error('Failed to fetch demo personas');
    return res.json();
  },

  async searchBySelfie(eventId: string, file?: File | Blob, personaId?: string): Promise<SearchResponse> {
    const formData = new FormData();
    if (file) {
      formData.append('selfie', file);
    }
    if (personaId) {
      formData.append('persona_id', personaId);
    }

    const res = await fetch(`${API_BASE}/events/${eventId}/search`, {
      method: 'POST',
      body: formData
    });
    if (!res.ok) {
      const err = await res.json().catch(() => null);
      throw new Error(err?.detail || 'Failed to perform face search');
    }
    return res.json();
  },

  async searchByBib(eventId: string, bibNumber: string): Promise<SearchResponse> {
    const formData = new FormData();
    formData.append('bib_number', bibNumber);

    const res = await fetch(`${API_BASE}/events/${eventId}/bib-search`, {
      method: 'POST',
      body: formData
    });
    if (!res.ok) {
      const err = await res.json().catch(() => null);
      throw new Error(err?.detail || 'Failed to perform bib search');
    }
    return res.json();
  },

  async uploadPhoto(
    eventId: string,
    file: File,
    meta?: { captured_time?: string; location?: string; photographer?: string; bib_numbers_str?: string }
  ): Promise<Photo> {
    const formData = new FormData();
    formData.append('file', file);
    if (meta?.captured_time) formData.append('captured_time', meta.captured_time);
    if (meta?.location) formData.append('location', meta.location);
    if (meta?.photographer) formData.append('photographer', meta.photographer);
    if (meta?.bib_numbers_str) formData.append('bib_numbers_str', meta.bib_numbers_str);

    const res = await fetch(`${API_BASE}/events/${eventId}/photos`, {
      method: 'POST',
      body: formData
    });
    if (!res.ok) {
      const err = await res.json().catch(() => null);
      throw new Error(err?.detail || 'Failed to upload photo');
    }
    return res.json();
  },

  async likePhoto(photoId: string): Promise<{ id: string; likes: number }> {
    const res = await fetch(`${API_BASE}/photos/${photoId}/like`, { method: 'POST' });
    if (!res.ok) throw new Error('Failed to like photo');
    return res.json();
  },

  async deleteSearchData(): Promise<{ status: string; message: string; cleared_records: number }> {
    const res = await fetch(`${API_BASE}/search-data`, { method: 'DELETE' });
    if (!res.ok) throw new Error('Failed to delete search data');
    return res.json();
  },

  async getPhotographerStats(): Promise<PhotographerStats> {
    const res = await fetch(`${API_BASE}/photographer/stats`);
    if (!res.ok) throw new Error('Failed to fetch photographer stats');
    return res.json();
  },

  async getCloudinaryStatus(): Promise<{
    cloud_name: string;
    is_live_connected: boolean;
    engine_mode: string;
    transformations_active: string[];
    hackathon_track: string;
  }> {
    const res = await fetch(`${API_BASE}/cloudinary/status`);
    if (!res.ok) throw new Error('Failed to fetch Cloudinary status');
    return res.json();
  },

  async startDriveImport(eventId: string, folderUrl: string): Promise<ImportJob> {
    const res = await fetch(`${API_BASE}/events/${encodeURIComponent(eventId)}/imports/google-drive`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ folder_url: folderUrl })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => null);
      throw new Error(err?.detail || 'Failed to start Google Drive import');
    }
    return res.json();
  },

  async getImportJob(jobId: string): Promise<ImportJob> {
    const res = await fetch(`${API_BASE}/imports/${encodeURIComponent(jobId)}`);
    if (!res.ok) throw new Error('Failed to fetch import status');
    return res.json();
  },

  async cancelImportJob(jobId: string): Promise<ImportJob> {
    const res = await fetch(`${API_BASE}/imports/${encodeURIComponent(jobId)}/cancel`, { method: 'POST' });
    if (!res.ok) throw new Error('Failed to cancel import');
    return res.json();
  },

  async updateCloudinaryConfig(config: { cloud_name: string; api_key?: string; api_secret?: string }) {
    const res = await fetch(`${API_BASE}/cloudinary/config`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config)
    });
    if (!res.ok) throw new Error('Failed to update Cloudinary config');
    return res.json();
  }
};
