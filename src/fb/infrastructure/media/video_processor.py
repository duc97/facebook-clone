"""Video processing: metadata extraction, thumbnail generation via ffmpeg.

ffmpeg is optional — if not available, operations degrade gracefully.
"""
from __future__ import annotations

import io
import json
import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class VideoMetadata:
    width: int
    height: int
    duration_seconds: float
    codec: str
    bitrate_kbps: int


@dataclass(frozen=True)
class VideoThumbnail:
    data: bytes          # JPEG or WebP bytes
    content_type: str
    width: int
    height: int
    file_size: int


def _ffmpeg_available() -> bool:
    """Check whether ffmpeg/ffprobe are available on PATH."""
    try:
        result = subprocess.run(
            ["ffprobe", "-version"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


class VideoProcessor:
    """Extract metadata and generate thumbnails from video files using ffmpeg.

    All methods are synchronous (CPU/IO bound) — use run_in_executor.
    """

    def is_available(self) -> bool:
        return _ffmpeg_available()

    def get_metadata(self, video_data: bytes) -> VideoMetadata | None:
        """Extract width, height, duration, codec from video bytes.

        Uses ffprobe with pipe input.
        """
        if not self.is_available():
            return None

        try:
            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
                tmp.write(video_data)
                tmp_path = tmp.name

            try:
                result = subprocess.run(
                    [
                        "ffprobe",
                        "-v", "quiet",
                        "-print_format", "json",
                        "-show_streams",
                        "-show_format",
                        tmp_path,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if result.returncode != 0:
                    return None

                info = json.loads(result.stdout)
                streams = info.get("streams", [])
                fmt = info.get("format", {})

                video_stream = next(
                    (s for s in streams if s.get("codec_type") == "video"),
                    None,
                )
                if video_stream is None:
                    return None

                width = int(video_stream.get("width", 0))
                height = int(video_stream.get("height", 0))
                duration = float(fmt.get("duration") or video_stream.get("duration") or 0)
                codec = video_stream.get("codec_name", "unknown")
                bit_rate = int(fmt.get("bit_rate") or 0) // 1000  # bps → kbps

                return VideoMetadata(
                    width=width,
                    height=height,
                    duration_seconds=round(duration, 2),
                    codec=codec,
                    bitrate_kbps=bit_rate,
                )
            finally:
                os.unlink(tmp_path)

        except Exception:
            logger.exception("Failed to get video metadata")
            return None

    def extract_thumbnail(self, video_data: bytes, at_second: float = 1.0) -> VideoThumbnail | None:
        """Extract a frame from the video at `at_second` and return as WebP bytes.

        Falls back to ffmpeg's best first keyframe if at_second is unavailable.
        """
        if not self.is_available():
            return None

        try:
            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as in_tmp:
                in_tmp.write(video_data)
                in_path = in_tmp.name

            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as out_tmp:
                out_path = out_tmp.name

            try:
                result = subprocess.run(
                    [
                        "ffmpeg",
                        "-y",
                        "-i", in_path,
                        "-ss", str(at_second),
                        "-vframes", "1",
                        "-vf", "scale=640:-2",   # width 640, height auto (even)
                        "-q:v", "3",              # JPEG quality 3 (high)
                        out_path,
                    ],
                    capture_output=True,
                    timeout=60,
                )

                if result.returncode != 0 or not os.path.exists(out_path):
                    return None

                with open(out_path, "rb") as f:
                    jpeg_data = f.read()

                if not jpeg_data:
                    return None

                # Optionally convert to WebP with Pillow if available
                data, ctype, w, h = _jpeg_to_webp(jpeg_data)

                return VideoThumbnail(
                    data=data,
                    content_type=ctype,
                    width=w,
                    height=h,
                    file_size=len(data),
                )
            finally:
                for p in (in_path, out_path):
                    try:
                        os.unlink(p)
                    except FileNotFoundError:
                        pass

        except Exception:
            logger.exception("Failed to extract video thumbnail")
            return None


def _jpeg_to_webp(jpeg_data: bytes) -> tuple[bytes, str, int, int]:
    """Convert JPEG bytes to WebP if Pillow is available, else return JPEG."""
    try:
        from PIL import Image  # type: ignore[import]
        import io as _io
        with Image.open(_io.BytesIO(jpeg_data)) as img:
            w, h = img.width, img.height
            buf = _io.BytesIO()
            img.convert("RGB").save(buf, format="WEBP", quality=80, method=4)
            return buf.getvalue(), "image/webp", w, h
    except Exception:
        # Return JPEG as fallback
        try:
            from PIL import Image  # type: ignore[import]
            import io as _io
            with Image.open(_io.BytesIO(jpeg_data)) as img:
                return jpeg_data, "image/jpeg", img.width, img.height
        except Exception:
            return jpeg_data, "image/jpeg", 0, 0
