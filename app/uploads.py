"""Avatar upload: resize to a square 512px webp, save to app/static/uploads.

For prod on Fly, mount a volume at /app/app/static/uploads so uploads survive restarts.
"""
import io
import secrets
from pathlib import Path
from PIL import Image, ImageOps

UPLOAD_DIR = Path("app/static/uploads")
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
    return f"/static/uploads/{name}"
