from typing import Optional
from fastapi import Request, HTTPException, Depends
from sqlmodel import Session, select
from slugify import slugify
import secrets

from .db import get_session
from .models import User


def current_user(request: Request, session: Session = Depends(get_session)) -> Optional[User]:
    uid = request.session.get("uid")
    if not uid:
        return None
    return session.get(User, uid)


def require_user(request: Request, session: Session = Depends(get_session)) -> User:
    user = current_user(request, session)
    if not user:
        raise HTTPException(status_code=401, detail="login required")
    return user


def make_unique_slug(session: Session, base: str) -> str:
    base_slug = slugify(base) or "user"
    slug = base_slug
    i = 0
    while session.exec(select(User).where(User.slug == slug)).first():
        i += 1
        slug = f"{base_slug}-{i}"
    return slug


def upsert_user_from_google(
    session: Session,
    *,
    sub: str,
    email: str,
    name: str,
    picture: str,
) -> User:
    user = session.exec(select(User).where(User.google_sub == sub)).first()
    if user:
        # refresh display data
        if name and not user.name:
            user.name = name
        if picture and not user.picture_url:
            user.picture_url = picture
        session.add(user)
        session.commit()
        session.refresh(user)
        return user

    slug = make_unique_slug(session, name or email.split("@")[0])
    user = User(
        google_sub=sub,
        email=email,
        name=name or email.split("@")[0],
        picture_url=picture or "",
        slug=slug,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def fake_login_user(session: Session, email: str, name: str) -> User:
    """Dev-only: log in (or create) a user without real Google OAuth."""
    sub = f"fake|{email}"
    return upsert_user_from_google(
        session,
        sub=sub,
        email=email,
        name=name,
        picture=f"https://api.dicebear.com/9.x/thumbs/svg?seed={secrets.token_hex(4)}",
    )
