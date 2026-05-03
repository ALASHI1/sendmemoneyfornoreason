"""Avatar upload: resize to a square 512px webp, save to UPLOAD_DIR.

Set UPLOAD_DIR (and optionally UPLOAD_URL_PREFIX) to point at a persistent
location. On Fly, mount a volume at /data and set UPLOAD_DIR=/data/uploads.
"""
import io
import os
import secrets
from pathlib import Path
from PIL import Image, ImageOps

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "app/static/uploads"))
UPLOAD_URL_PREFIX = os.getenv("UPLOAD_URL_PREFIX", "/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_BYTES = 5 * 1024 * 1024  # 5 MB
ALLOWED = {"image/jpeg", "image/png", "image/webp", "image/gif"}


def save_avatar(file_bytes: bytes, content_type: str) -> str:
    if content_type not in ALLOWED:
        raise ValueError("unsupported image type")
    if len(file_bytes) > MAX_BYTES:
        raise ValueError("image too large (max 5MB)")
    img = Image.open(io.BytesIO(file_bytes))
    img = ImageOps.exif_transpose(img).convert("RGB")
    img = ImageOps.fit(img, (512, 512), Image.LANCZOS)
    name = f"{secrets.token_hex(12)}.webp"
    path = UPLOAD_DIR / name
    img.save(path, "WEBP", quality=85, method=6)
    return f"{UPLOAD_URL_PREFIX.rstrip('/')}/{name}"
