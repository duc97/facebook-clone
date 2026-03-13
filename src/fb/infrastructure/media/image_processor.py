"""Image processing: resize, compress, generate thumbnails, convert to WebP."""
from __future__ import annotations

import io
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Lazy import Pillow to avoid hard dep at import time
try:
    from PIL import Image, ImageOps
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False
    logger.warning("Pillow not installed — image processing disabled")


@dataclass(frozen=True)
class ImageDimensions:
    width: int
    height: int


@dataclass(frozen=True)
class ProcessedImage:
    data: bytes
    content_type: str
    width: int
    height: int
    file_size: int


@dataclass(frozen=True)
class ThumbnailResult:
    data: bytes
    content_type: str
    width: int
    height: int
    file_size: int


# ── Config constants ──────────────────────────────────────────────────

# Max dimension for "processed" (display) images
MAX_DISPLAY_WIDTH = 1920
MAX_DISPLAY_HEIGHT = 1080

# Thumbnail size
THUMBNAIL_SIZE = (320, 320)

# JPEG/WebP quality
IMAGE_QUALITY = 85
THUMBNAIL_QUALITY = 75


class ImageProcessor:
    """Resize, compress, and thumbnail images using Pillow.

    All operations are CPU-bound and synchronous — call from a thread pool
    executor in async contexts via ``asyncio.get_event_loop().run_in_executor``.
    """

    def is_available(self) -> bool:
        return _PIL_AVAILABLE

    def get_dimensions(self, image_data: bytes) -> ImageDimensions | None:
        """Return (width, height) of image, or None if not parseable."""
        if not _PIL_AVAILABLE:
            return None
        try:
            with Image.open(io.BytesIO(image_data)) as img:
                return ImageDimensions(width=img.width, height=img.height)
        except Exception:
            logger.exception("Failed to read image dimensions")
            return None

    def process(self, image_data: bytes, content_type: str) -> ProcessedImage:
        """Resize to max display dimensions and compress.

        - If image is smaller than MAX_DISPLAY, keep original size
        - Convert JPEG/PNG to WebP for better compression (unless GIF)
        - Returns ProcessedImage with new bytes, content_type, dimensions
        """
        if not _PIL_AVAILABLE:
            # Pass-through if Pillow not available
            return ProcessedImage(
                data=image_data,
                content_type=content_type,
                width=0,
                height=0,
                file_size=len(image_data),
            )

        with Image.open(io.BytesIO(image_data)) as img:
            # Fix orientation from EXIF
            img = ImageOps.exif_transpose(img) or img

            # Convert RGBA/P mode images to RGB for JPEG/WebP
            if img.mode in ("RGBA", "P") and content_type != "image/gif":
                img = img.convert("RGBA")  # keep alpha for WebP
            elif img.mode not in ("RGB", "RGBA", "L"):
                img = img.convert("RGB")

            original_w, original_h = img.width, img.height

            # Resize if larger than max display dimensions
            if original_w > MAX_DISPLAY_WIDTH or original_h > MAX_DISPLAY_HEIGHT:
                img.thumbnail((MAX_DISPLAY_WIDTH, MAX_DISPLAY_HEIGHT), Image.LANCZOS)

            final_w, final_h = img.width, img.height

            # Choose output format
            if content_type == "image/gif":
                # Keep GIF as-is (animation support)
                buf = io.BytesIO()
                img.save(buf, format="GIF")
                out_type = "image/gif"
            else:
                # Convert to WebP for better compression
                buf = io.BytesIO()
                save_img = img.convert("RGBA") if img.mode == "RGBA" else img.convert("RGB")
                save_img.save(buf, format="WEBP", quality=IMAGE_QUALITY, method=4)
                out_type = "image/webp"

            data = buf.getvalue()

        return ProcessedImage(
            data=data,
            content_type=out_type,
            width=final_w,
            height=final_h,
            file_size=len(data),
        )

    def generate_thumbnail(self, image_data: bytes, content_type: str) -> ThumbnailResult:
        """Generate a square thumbnail (cropped center).

        Returns ThumbnailResult with WebP bytes.
        """
        if not _PIL_AVAILABLE:
            return ThumbnailResult(
                data=image_data,
                content_type=content_type,
                width=THUMBNAIL_SIZE[0],
                height=THUMBNAIL_SIZE[1],
                file_size=len(image_data),
            )

        with Image.open(io.BytesIO(image_data)) as img:
            img = ImageOps.exif_transpose(img) or img

            # Center-crop to square before thumbnail
            w, h = img.width, img.height
            min_dim = min(w, h)
            left = (w - min_dim) // 2
            top = (h - min_dim) // 2
            img = img.crop((left, top, left + min_dim, top + min_dim))

            # Resize to thumbnail dimensions
            img = img.resize(THUMBNAIL_SIZE, Image.LANCZOS)

            # Convert to RGB for WebP output
            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGB")
            elif img.mode == "RGBA":
                pass  # WebP supports RGBA

            buf = io.BytesIO()
            img.save(buf, format="WEBP", quality=THUMBNAIL_QUALITY, method=4)
            data = buf.getvalue()

        return ThumbnailResult(
            data=data,
            content_type="image/webp",
            width=THUMBNAIL_SIZE[0],
            height=THUMBNAIL_SIZE[1],
            file_size=len(data),
        )
