"""
Reusable image decoding helper.

Strategy (smallest safe change for the existing pipeline):
1. Try the EXISTING OpenCV decode first (cv2.imdecode). For JPG/PNG and any
   other OpenCV-readable format, the ORIGINAL bytes are returned unchanged
   (is_heif_converted=False) - existing behavior is fully preserved.
2. If OpenCV cannot decode the bytes (HEIF/HEIC/HIF, some camera formats),
   fall back to Pillow + pillow-heif: apply EXIF orientation, convert to
   RGB, and re-encode as a high-quality JPEG (quality=95) that OpenCV
   (YuNet/SFace) can decode. (is_heif_converted=True)
3. If both fail, raise ImageDecodeError with a clear message.

Cloudinary should always receive the ORIGINAL bytes; the converted JPEG is
a temporary, CV-only artifact and never replaces the original upload.
"""
import io
from typing import Tuple

from PIL import Image, ImageOps

try:
    from pillow_heif import register_heif_opener

    register_heif_opener()
    _HEIF_AVAILABLE = True
except Exception:  # pragma: no cover - pillow-heif is a declared dependency
    _HEIF_AVAILABLE = False


class ImageDecodeError(Exception):
    pass


def _opencv_can_decode(file_bytes: bytes) -> bool:
    try:
        import cv2
        import numpy as np

        arr = np.frombuffer(file_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        return img is not None
    except Exception:
        return False


def _heif_bytes_to_jpeg(file_bytes: bytes) -> bytes:
    try:
        img = Image.open(io.BytesIO(file_bytes))
        img = ImageOps.exif_transpose(img)  # honor EXIF orientation
        img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=95)
        return buf.getvalue()
    except Exception as e:
        raise ImageDecodeError(
            "Image could not be decoded as HEIF/HEIC/HIF (possibly corrupt or unsupported). "
            f"Details: {e}"
        )


def image_bytes_for_opencv(file_bytes: bytes) -> Tuple[bytes, bool]:
    """Returns (bytes_for_opencv, is_heif_converted).

    Normal formats pass through unchanged; HEIF/HEIC/HIF is converted to a
    temporary high-quality JPEG for the CV pipeline only.
    Raises ImageDecodeError when nothing can decode the bytes.
    """
    if len(file_bytes) == 0:
        raise ImageDecodeError("Empty image data")

    if _opencv_can_decode(file_bytes):
        return file_bytes, False

    # OpenCV could not read it -> try HEIF/HEIC/HIF via Pillow
    return _heif_bytes_to_jpeg(file_bytes), True


def can_be_decoded(file_bytes: bytes) -> bool:
    try:
        image_bytes_for_opencv(file_bytes)
        return True
    except ImageDecodeError:
        return False
