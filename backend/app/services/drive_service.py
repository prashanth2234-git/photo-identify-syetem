"""
Google Drive integration (official Google Drive API only - no HTML scraping).

Authentication priority:
  1. Service Account (PRIMARY): photographer shares the folder with the
     service-account email as Viewer. Configure via
     GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE (path to JSON key) or
     GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON (raw JSON key content).
  2. API key (FALLBACK): only works for folders shared as
     "Anyone with the link". Configure via GOOGLE_DRIVE_API_KEY.

Supports both My Drive folders and Shared Drive (Team Drive) folders.
"""
import io
import json
import os
import re
import time
from typing import Any, Dict, Iterator, List, Optional

from app.config import settings  # noqa: F401  (ensures .env is loaded)

DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.readonly"
FOLDER_MIME = "application/vnd.google-apps.folder"
SHORTCUT_MIME = "application/vnd.google-apps.shortcut"


class DriveConfigError(Exception):
    """Missing or invalid Google Drive server configuration."""


class DriveURLError(Exception):
    """Malformed Google Drive folder URL / ID."""


class DriveAccessError(Exception):
    """Folder inaccessible, not found, or not shared with the service account."""


def extract_folder_id(folder_url_or_id: str) -> str:
    """Parses a Google Drive folder URL or raw folder ID into a folder ID."""
    if not folder_url_or_id or not folder_url_or_id.strip():
        raise DriveURLError("Empty Google Drive folder URL provided.")

    text = folder_url_or_id.strip()

    # /folders/<id> style URLs (My Drive & Shared Drive)
    m = re.search(r"/folders/([-\w]+)", text)
    if m:
        return m.group(1)

    # ?id=<id> style URLs
    m = re.search(r"[?&]id=([-\w]+)", text)
    if m:
        return m.group(1)

    # Raw folder ID passed directly
    if re.fullmatch(r"[-\w]{10,}", text):
        return text

    raise DriveURLError(
        "Could not parse a Google Drive folder ID from the provided URL. "
        "Expected a URL like https://drive.google.com/drive/folders/<folder-id>"
    )


def _service_account_credentials():
    from google.oauth2 import service_account

    sa_file = os.getenv("GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE", "").strip()
    sa_json = os.getenv("GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON", "").strip()

    if sa_file:
        if not os.path.exists(sa_file):
            raise DriveConfigError(
                f"GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE points to a missing file: {sa_file}"
            )
        try:
            return service_account.Credentials.from_service_account_file(
                sa_file, scopes=[DRIVE_SCOPE]
            )
        except Exception as e:
            raise DriveConfigError(f"Invalid service account key file: {e}")

    if sa_json:
        try:
            info = json.loads(sa_json)
        except Exception:
            raise DriveConfigError("GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON is not valid JSON.")
        try:
            return service_account.Credentials.from_service_account_info(
                info, scopes=[DRIVE_SCOPE]
            )
        except Exception as e:
            raise DriveConfigError(f"Invalid service account credentials: {e}")

    return None


def get_drive_service():
    """Builds an authenticated Google Drive API client.

    Service account is the primary method; API key is the fallback for
    public ("Anyone with the link") folders only.
    """
    try:
        from googleapiclient.discovery import build
    except ImportError:
        raise DriveConfigError(
            "google-api-python-client is not installed. "
            "Run: pip install google-api-python-client google-auth google-auth-httplib2"
        )

    creds = _service_account_credentials()
    if creds is not None:
        try:
            return build("drive", "v3", credentials=creds, cache_discovery=False)
        except Exception as e:
            raise DriveConfigError(f"Failed to initialize Google Drive client: {e}")

    api_key = os.getenv("GOOGLE_DRIVE_API_KEY", "").strip()
    if api_key:
        try:
            return build("drive", "v3", developerKey=api_key, cache_discovery=False)
        except Exception as e:
            raise DriveConfigError(f"Failed to initialize Google Drive client: {e}")

    raise DriveConfigError(
        "Google Drive is not configured on the server. Set "
        "GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE (or GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON), "
        "or GOOGLE_DRIVE_API_KEY for public folders."
    )


def _http_error_message(e: Exception) -> str:
    try:
        from googleapiclient.errors import HttpError

        if isinstance(e, HttpError):
            status = getattr(e.resp, "status", None) or getattr(e.resp, "status_code", None)
            if str(status) in ("404",):
                return "Folder not found. Verify the link and that the folder is shared with the EventSnap service account as Viewer."
            if str(status) in ("403",):
                return "Access denied. Share the folder with the EventSnap service account email as Viewer, or check Google API quota."
            if str(status) in ("401",):
                return "Invalid or revoked Google credentials on the server."
            return f"Google Drive API error (HTTP {status})."
    except ImportError:
        pass
    return str(e)


def get_folder_metadata(service, folder_id: str) -> Dict[str, Any]:
    """Validates access to the folder and returns its metadata."""
    try:
        return (
            service.files()
            .get(
                fileId=folder_id,
                fields="id,name,mimeType,driveId",
                supportsAllDrives=True,
            )
            .execute()
        )
    except Exception as e:
        raise DriveAccessError(_http_error_message(e))


def iter_folder_files(service, folder_id: str, max_files: int = 1000) -> Iterator[Dict[str, Any]]:
    """Yields image-file metadata dicts that are DIRECT children of folder_id.

    Non-recursive by design: nested subfolders are not traversed, so
    importing "folder X" imports only the images sitting directly inside X.
    Uses supportsAllDrives / includeItemsFromAllDrives / corpora=allDrives
    so both My Drive and Shared Drive folders work. Pages results so the
    entire listing is never held in memory beyond a single page.
    """
    page_token = None
    yielded = 0

    while True:
        try:
            resp = (
                service.files()
                .list(
                    q=(
                        f"'{folder_id}' in parents and trashed = false "
                        "and mimeType contains 'image/'"
                    ),
                    fields="nextPageToken, files(id, name, mimeType, size)",
                    pageSize=100,
                    pageToken=page_token,
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True,
                    corpora="allDrives",
                )
                .execute()
            )
        except Exception as e:
            raise DriveAccessError(_http_error_message(e))

        for f in resp.get("files", []):
            if not f.get("mimeType", "").startswith("image/"):
                continue
            yield f
            yielded += 1
            if yielded >= max_files:
                return

        page_token = resp.get("nextPageToken")
        if not page_token:
            break


def download_file(service, file_id: str, max_attempts: int = 3) -> bytes:
    """Downloads a single file into memory with retry on transient errors."""
    from googleapiclient.http import MediaIoBaseDownload

    last_error: Optional[Exception] = None
    for attempt in range(max_attempts):
        try:
            request = service.files().get_media(fileId=file_id, supportsAllDrives=True)
            buf = io.BytesIO()
            downloader = MediaIoBaseDownload(buf, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
            data = buf.getvalue()
            del buf, downloader
            return data
        except Exception as e:
            last_error = e
            from googleapiclient.errors import HttpError

            status = None
            if isinstance(e, HttpError):
                status = getattr(e.resp, "status", None) or getattr(e.resp, "status_code", None)
            transient = status is None or str(status) in ("403", "429", "500", "502", "503", "504")
            if not transient or attempt == max_attempts - 1:
                break
            time.sleep(1.5 * (attempt + 1))

    raise DriveAccessError(f"Download failed: {_http_error_message(last_error)}")
