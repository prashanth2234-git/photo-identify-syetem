export interface Photo {
  id: string;
  event_id: string;
  original_url: string;
  cloudinary_public_id: string;
  thumbnail_url: string;
  watermarked_url: string;
  captured_time: string;
  location: string;
  photographer: string;
  camera_meta: string;
  bib_numbers: string[];
  faces_detected?: number;
  width: number;
  height: number;
  likes: number;
}

export interface Event {
  id: string;
  title: string;
  type: string; // Sports, Wedding, College, Conference, Concert, Corporate, Other
  date: string;
  location: string;
  description: string;
  cover_url: string;
  total_photos: number;
  views: number;
  searches: number;
  photographer_name: string;
  created_at: string;
}

export interface SearchResult {
  photo: Photo;
  confidence_score: number;
  match_type: 'face' | 'bib';
  detected_bib?: string;
}

export interface SearchResponse {
  event_id: string;
  event_title: string;
  query_type: 'selfie' | 'bib' | 'gallery';
  total_matches: number;
  results: SearchResult[];
  processing_time_ms: number;
  message: string;
}

export interface DemoPersona {
  id: string;
  name: string;
  event_id: string;
  event_name: string;
  role_description: string;
  selfie_url: string;
  bib_number?: string;
}

export interface PhotographerStats {
  total_events: number;
  total_photos: number;
  total_searches: number;
  total_views: number;
  conversion_rate: number;
  active_cloud: string;
  cloud_status: string;
}

export interface CreateEventPayload {
  title: string;
  type: string;
  date: string;
  location: string;
  description: string;
  cover_url?: string;
  photographer_name?: string;
}

export interface ImportJob {
  id: string;
  event_id: string;
  folder_url: string;
  status: 'queued' | 'running' | 'completed' | 'completed_with_errors' | 'failed' | 'cancelled';
  total: number;
  processed: number;
  successful: number;
  skipped: number;
  failed: number;
  remaining: number;
  percentage: number;
  current_filename: string | null;
  message: string;
  errors: Array<{ file: string; error: string }>;
  created_at: string;
  finished_at: string | null;
}

export interface UploadItem {
  id: string;
  file: File;
  name: string;
  size: string;
  progress: number;
  status: 'pending' | 'uploading' | 'processing' | 'indexed' | 'error';
  previewUrl: string;
  cloudinaryUrl?: string;
  publicId?: string;
  facesDetected?: number;
  error?: string;
}

