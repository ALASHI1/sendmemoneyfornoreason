from fastapi import APIRouter, Request, Depends, HTTPException, Form, UploadFile, File
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from ..db import get_session
from ..models import User, PaymentLink
from ..auth import current_user, require_user
from .. import payment_kinds as pk
from ..payment_kinds import KINDS, is_valid_kind, kind_spec
from ..config import DEV_FAKE_LOGIN, GOOGLE_CLIENT_ID
from ..uploads import save_avatar

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
templates.env.globals["KINDS"] = KINDS
templates.env.globals["pay_url"] = pk.pay_url
templates.env.globals["qr_data"] = pk.qr_data
templates.env.globals["link_summary"] = pk.summary
templates.env.globals["kind_icon"] = pk.kind_icon


def _ctx(request: Request, user: User | None, **extra):
    return {
        "request": request,
        "user": user,
        "KINDS": KINDS,
        "DEV_FAKE_LOGIN": DEV_FAKE_LOGIN,
        "GOOGLE_OAUTH_ENABLED": bool(GOOGLE_CLIENT_ID),
        **extra,
    }


@router.get("/", response_class=HTMLResponse)
def feed(request: Request, session: Session = Depends(get_session)):
    user = current_user(request, session)
    users = session.exec(select(User).order_by(User.created_at.desc()).limit(120)).all()
    cards = []
    for u in users:
        links = session.exec(select(PaymentLink).where(PaymentLink.user_id == u.id)).all()
        if not links:
            continue
        cards.append({"user": u, "links": links})
    return templates.TemplateResponse("feed.html", _ctx(request, user, cards=cards))


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, session: Session = Depends(get_session)):
    user = current_user(request, session)
    if user:
        return RedirectResponse("/me", status_code=303)
    return templates.TemplateResponse("login.html", _ctx(request, None))


@router.get("/me", response_class=HTMLResponse)
def me(request: Request, user: User = Depends(require_user), session: Session = Depends(get_session)):
    links = session.exec(
        select(PaymentLink).where(PaymentLink.user_id == user.id).order_by(PaymentLink.sort_order, PaymentLink.id)
    ).all()
    return templates.TemplateResponse("me.html", _ctx(request, user, links=links))


@router.post("/me/profile")
async def update_profile(
    request: Request,
    name: str = Form(""),
    picture: UploadFile | None = File(None),
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
):
    user.name = name.strip() or user.name
    if picture and picture.filename:
        data = await picture.read()
        if data:
            try:
                user.picture_url = save_avatar(data, picture.content_type or "")
            except ValueError as e:
                raise HTTPException(400, str(e))
    session.add(user)
    session.commit()
    return RedirectResponse("/me", status_code=303)


@router.post("/me/links")
async def add_link(
    request: Request,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
):
    form = await request.form()
    kind = (form.get("kind") or "").strip()
    if not is_valid_kind(kind):
        raise HTTPException(400, "unknown kind")
    spec = kind_spec(kind)
    raw = {f["name"]: form.get(f"{kind}__{f['name']}", "") for f in spec["fields"]}
    try:
        meta = spec["validate"](raw)
    except ValueError as e:
        raise HTTPException(400, str(e))
    link = PaymentLink(user_id=user.id, kind=kind, meta=meta)
    session.add(link)
    session.commit()
    return RedirectResponse("/me", status_code=303)


@router.post("/me/links/{link_id}/delete")
def delete_link(
    link_id: int,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
):
    link = session.get(PaymentLink, link_id)
    if not link or link.user_id != user.id:
        raise HTTPException(404)
    session.delete(link)
    session.commit()
    return RedirectResponse("/me", status_code=303)


@router.get("/u/{slug}", response_class=HTMLResponse)
def public_profile(slug: str, request: Request, session: Session = Depends(get_session)):
    me_user = current_user(request, session)
    target = session.exec(select(User).where(User.slug == slug)).first()
    if not target:
        raise HTTPException(404, "not found")
    links = session.exec(
        select(PaymentLink).where(PaymentLink.user_id == target.id).order_by(PaymentLink.sort_order, PaymentLink.id)
    ).all()
    return templates.TemplateResponse(
        "profile.html",
        _ctx(request, me_user, target=target, links=links),
    )
