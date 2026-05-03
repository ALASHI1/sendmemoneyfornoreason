# sendmemoneyfornoreason

Tiny FastAPI site. Sign in with Google, drop your bank / crypto / paypal / cashapp / whatever, share your page, get paid for no reason.

## Stack
- **FastAPI** + **SQLModel** (Postgres in prod, SQLite locally)
- **Authlib** for Google OAuth (only login method)
- **Jinja2** templates, vanilla CSS — no build step
- **Docker** for portable deploys (Fly.io, Render, Railway)

## Local dev

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
# open http://localhost:8000
```

`DEV_FAKE_LOGIN=1` is on by default in `.env.example` so you can fake-login without setting up Google OAuth. Turn it off in prod.

## Google OAuth setup

1. Go to https://console.cloud.google.com/apis/credentials
2. Create an OAuth client (Web application).
3. Authorized redirect URI: `https://sendmemoneyfornoreason.com/auth/callback` (and `http://localhost:8000/auth/callback` for dev).
4. Copy client ID + secret into `.env` (or your host's secrets).

## Free DB

[Neon](https://neon.tech) free tier — create a project, copy the Postgres URL into `DATABASE_URL`. (Supabase works the same way.)

## Deploy: Fly.io (recommended)

```bash
fly launch --no-deploy        # claim app name in fly.toml
fly secrets set \
  SECRET_KEY=$(python -c 'import secrets;print(secrets.token_urlsafe(48))') \
  DATABASE_URL='postgres://...neon...' \
  GOOGLE_CLIENT_ID='...' \
  GOOGLE_CLIENT_SECRET='...' \
  BASE_URL='https://sendmemoneyfornoreason.com' \
  DEV_FAKE_LOGIN=0
fly deploy
fly certs add sendmemoneyfornoreason.com
```

Point your domain's DNS at the Fly cert instructions.

## Deploy: Render

Push to GitHub, click **New +** → **Blueprint**, point to this repo. `render.yaml` provisions the free web service. Set `DATABASE_URL`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `BASE_URL` in the dashboard.

## Routes

- `/` — public feed
- `/login` — google or (dev) fake login
- `/me` — edit profile + manage links
- `/u/{slug}` — public profile
- `/healthz` — health check
