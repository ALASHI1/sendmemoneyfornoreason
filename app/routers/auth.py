from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import RedirectResponse
from authlib.integrations.starlette_client import OAuth
from sqlmodel import Session

from ..config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, DEV_FAKE_LOGIN
from ..db import get_session
from ..auth import upsert_user_from_google, fake_login_user

router = APIRouter()
oauth = OAuth()

if GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET:
    oauth.register(
        name="google",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )


@router.get("/login/google")
async def login_google(request: Request):
    if not (GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET):
        raise HTTPException(503, "Google OAuth not configured. Set GOOGLE_CLIENT_ID/SECRET or use /login/dev.")
    redirect_uri = request.url_for("auth_callback")
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/auth/callback", name="auth_callback")
async def auth_callback(request: Request, session: Session = Depends(get_session)):
    token = await oauth.google.authorize_access_token(request)
    info = token.get("userinfo") or {}
    if not info:
        raise HTTPException(400, "Could not read Google profile")
    user = upsert_user_from_google(
        session,
        sub=info["sub"],
        email=info.get("email", ""),
        name=info.get("name", ""),
        picture=info.get("picture", ""),
    )
    request.session["uid"] = user.id
    return RedirectResponse("/me", status_code=303)


@router.post("/login/dev")
def login_dev(
    request: Request,
    email: str = Form(...),
    name: str = Form(""),
    session: Session = Depends(get_session),
):
    if not DEV_FAKE_LOGIN:
        raise HTTPException(403, "dev login disabled")
    user = fake_login_user(session, email=email, name=name or email.split("@")[0])
    request.session["uid"] = user.id
    return RedirectResponse("/me", status_code=303)


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)
