import io
import qrcode
from fastapi import APIRouter, Query
from fastapi.responses import Response

router = APIRouter()

MAX_LEN = 1024  # cap to prevent abuse


@router.get("/qr.png")
def qr_png(data: str = Query(..., min_length=1, max_length=MAX_LEN)):
    img = qrcode.make(data, border=2, box_size=8)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(
        content=buf.getvalue(),
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=86400, immutable"},
    )
