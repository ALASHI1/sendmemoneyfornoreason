"""Per-kind registry: input fields, validators, pay-URL builders, render hints.

Each kind defines:
- label, icon (emoji)
- fields: list of {name, label, placeholder, required, type}
- validate(meta) -> meta (cleaned)  | raises ValueError
- pay_url(meta) -> str | None       (canonical Pay button URL)
- qr_data(meta) -> str | None       (what to encode in a QR)
- summary(meta) -> str              (one-line for cards/lists)
- renderer: 'url' | 'handle' | 'bank' | 'crypto' | 'copy'
"""
from __future__ import annotations
import re
from typing import Optional
from urllib.parse import urlparse, quote

# ---------- helpers ----------

_HANDLE_RE = re.compile(r"^[A-Za-z0-9_.-]{2,40}$")
_BTC_RE = re.compile(r"^(bc1[a-z0-9]{8,87}|[13][a-zA-HJ-NP-Z0-9]{25,39})$")
_ETH_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")
_SOL_RE = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")
_TRON_RE = re.compile(r"^T[1-9A-HJ-NP-Za-km-z]{33}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_RE = re.compile(r"^[+\d][\d\s\-()]{6,20}$")


def _clean_handle(s: str) -> str:
    return s.strip().lstrip("@$").strip()


def _require_url(s: str, hosts: tuple[str, ...]) -> str:
    s = s.strip()
    p = urlparse(s)
    if p.scheme not in ("http", "https") or not p.netloc:
        raise ValueError("must be a full https URL")
    host = p.netloc.lower()
    if not any(host == h or host.endswith("." + h) for h in hosts):
        raise ValueError(f"URL must be on one of: {', '.join(hosts)}")
    return s


# ---------- per-kind specs ----------

def _bank_validate(m: dict) -> dict:
    out = {k: (v or "").strip() for k, v in m.items()}
    if not out.get("account_name"):
        raise ValueError("account holder name required")
    if not out.get("bank_name"):
        raise ValueError("bank name required")
    if not out.get("account_number") and not out.get("iban"):
        raise ValueError("account number or IBAN required")
    return out


def _bank_summary(m: dict) -> str:
    n = m.get("account_number") or m.get("iban") or ""
    masked = ("•" * max(0, len(n) - 4)) + n[-4:] if n else ""
    return f"{m.get('bank_name', '')} · {masked}".strip(" ·")


def _stripe_validate(m: dict) -> dict:
    return {"url": _require_url(m.get("url", ""), ("stripe.com",))}


def _paystack_validate(m: dict) -> dict:
    return {"url": _require_url(m.get("url", ""), ("paystack.com", "paystack.shop"))}


def _custom_validate(m: dict) -> dict:
    s = (m.get("url") or "").strip()
    p = urlparse(s)
    if p.scheme not in ("http", "https") or not p.netloc:
        raise ValueError("must be a full https URL")
    return {"url": s, "label": (m.get("label") or "").strip()}


def _handle_validate(m: dict) -> dict:
    h = _clean_handle(m.get("handle", ""))
    if not _HANDLE_RE.match(h):
        raise ValueError("handle must be 2-40 chars (letters, digits, _ . -)")
    return {"handle": h}


def _zelle_validate(m: dict) -> dict:
    s = (m.get("contact") or "").strip()
    if not (_EMAIL_RE.match(s) or _PHONE_RE.match(s)):
        raise ValueError("enter the email or phone linked to your Zelle")
    return {"contact": s}


def _crypto_validate(m: dict) -> dict:
    network = (m.get("network") or "").strip().lower()
    addr = (m.get("address") or "").strip()
    asset = (m.get("asset") or "").strip().upper() or {
        "btc": "BTC", "eth": "ETH", "sol": "SOL", "tron": "USDT",
    }.get(network, "")
    rules = {
        "btc": _BTC_RE,
        "eth": _ETH_RE,
        "sol": _SOL_RE,
        "tron": _TRON_RE,
    }
    if network not in rules:
        raise ValueError("pick a network (BTC, ETH, SOL, TRON)")
    if not rules[network].match(addr):
        raise ValueError(f"that doesn't look like a {network.upper()} address")
    return {"network": network, "address": addr, "asset": asset}


def _crypto_pay_url(m: dict) -> Optional[str]:
    n, a = m.get("network"), m.get("address")
    if n == "btc" and a:
        return f"bitcoin:{a}"
    if n == "eth" and a:
        return f"ethereum:{a}"
    if n == "sol" and a:
        return f"solana:{a}"
    return None  # TRON has no widely-supported deeplink


def _crypto_qr(m: dict) -> Optional[str]:
    return _crypto_pay_url(m) or m.get("address")


def _crypto_summary(m: dict) -> str:
    return f"{m.get('asset','')} · {m.get('network','').upper()}".strip(" ·")


KINDS: dict[str, dict] = {
    "bank": {
        "label": "Bank", "icon": "🏦", "renderer": "bank",
        "fields": [
            {"name": "account_name",   "label": "Account holder name", "required": True},
            {"name": "bank_name",      "label": "Bank name",           "required": True},
            {"name": "account_number", "label": "Account number",      "required": False},
            {"name": "iban",           "label": "IBAN",                "required": False},
            {"name": "routing_number", "label": "Routing / sort code", "required": False},
            {"name": "swift",          "label": "SWIFT / BIC",         "required": False},
            {"name": "country",        "label": "Country",             "required": False, "placeholder": "e.g. US, NG, GB"},
        ],
        "validate": _bank_validate,
        "pay_url":  lambda m: None,
        "qr_data":  lambda m: None,
        "summary":  _bank_summary,
    },

    "stripe": {
        "label": "Stripe", "icon": "💳", "renderer": "url",
        "fields": [{"name": "url", "label": "Stripe Payment Link URL", "required": True,
                    "placeholder": "https://buy.stripe.com/...", "type": "url"}],
        "validate": _stripe_validate,
        "pay_url":  lambda m: m["url"],
        "qr_data":  lambda m: m["url"],
        "summary":  lambda m: "Stripe checkout",
    },

    "paystack": {
        "label": "Paystack", "icon": "💳", "renderer": "url",
        "fields": [{"name": "url", "label": "Paystack Payment Page URL", "required": True,
                    "placeholder": "https://paystack.com/pay/...", "type": "url"}],
        "validate": _paystack_validate,
        "pay_url":  lambda m: m["url"],
        "qr_data":  lambda m: m["url"],
        "summary":  lambda m: "Paystack checkout",
    },

    "paypal": {
        "label": "PayPal", "icon": "🅿️", "renderer": "handle",
        "fields": [{"name": "handle", "label": "PayPal handle", "required": True,
                    "placeholder": "your-paypal-me-name"}],
        "validate": _handle_validate,
        "pay_url":  lambda m: f"https://paypal.me/{quote(m['handle'])}",
        "qr_data":  lambda m: f"https://paypal.me/{quote(m['handle'])}",
        "summary":  lambda m: f"paypal.me/{m['handle']}",
    },

    "cashapp": {
        "label": "Cash App", "icon": "💵", "renderer": "handle",
        "fields": [{"name": "handle", "label": "$cashtag", "required": True, "placeholder": "$yourtag"}],
        "validate": _handle_validate,
        "pay_url":  lambda m: f"https://cash.app/${quote(m['handle'])}",
        "qr_data":  lambda m: f"https://cash.app/${quote(m['handle'])}",
        "summary":  lambda m: f"${m['handle']}",
    },

    "venmo": {
        "label": "Venmo", "icon": "💸", "renderer": "handle",
        "fields": [{"name": "handle", "label": "Venmo handle", "required": True, "placeholder": "@yourhandle"}],
        "validate": _handle_validate,
        "pay_url":  lambda m: f"https://account.venmo.com/u/{quote(m['handle'])}",
        "qr_data":  lambda m: f"https://account.venmo.com/u/{quote(m['handle'])}",
        "summary":  lambda m: f"@{m['handle']}",
    },

    "kofi": {
        "label": "Ko-fi", "icon": "☕", "renderer": "handle",
        "fields": [{"name": "handle", "label": "Ko-fi handle", "required": True}],
        "validate": _handle_validate,
        "pay_url":  lambda m: f"https://ko-fi.com/{quote(m['handle'])}",
        "qr_data":  lambda m: f"https://ko-fi.com/{quote(m['handle'])}",
        "summary":  lambda m: f"ko-fi.com/{m['handle']}",
    },

    "buymeacoffee": {
        "label": "Buy Me a Coffee", "icon": "☕", "renderer": "handle",
        "fields": [{"name": "handle", "label": "BMC handle", "required": True}],
        "validate": _handle_validate,
        "pay_url":  lambda m: f"https://buymeacoffee.com/{quote(m['handle'])}",
        "qr_data":  lambda m: f"https://buymeacoffee.com/{quote(m['handle'])}",
        "summary":  lambda m: f"buymeacoffee.com/{m['handle']}",
    },

    "zelle": {
        "label": "Zelle", "icon": "🏛️", "renderer": "copy",
        "fields": [{"name": "contact", "label": "Email or phone (linked to Zelle)", "required": True,
                    "placeholder": "you@example.com or +1 555 555 5555"}],
        "validate": _zelle_validate,
        "pay_url":  lambda m: None,
        "qr_data":  lambda m: m["contact"],
        "summary":  lambda m: m["contact"],
    },

    "crypto": {
        "label": "Crypto", "icon": "₿", "renderer": "crypto",
        "fields": [
            {"name": "network", "label": "Network", "required": True, "type": "select",
             "options": [("btc", "Bitcoin"), ("eth", "Ethereum / EVM"), ("sol", "Solana"), ("tron", "Tron (TRC20)")]},
            {"name": "asset",   "label": "Asset (e.g. BTC, ETH, USDC, USDT)", "required": False,
             "placeholder": "BTC"},
            {"name": "address", "label": "Wallet address", "required": True,
             "placeholder": "bc1q... / 0x... / Tx... / ..."},
        ],
        "validate": _crypto_validate,
        "pay_url":  _crypto_pay_url,
        "qr_data":  _crypto_qr,
        "summary":  _crypto_summary,
    },

    "custom": {
        "label": "Custom link", "icon": "🔗", "renderer": "url",
        "fields": [
            {"name": "label", "label": "Label", "required": False, "placeholder": "what is this?"},
            {"name": "url",   "label": "URL",   "required": True,  "type": "url",
             "placeholder": "https://..."},
        ],
        "validate": _custom_validate,
        "pay_url":  lambda m: m["url"],
        "qr_data":  lambda m: m["url"],
        "summary":  lambda m: m.get("label") or m["url"],
    },
}


def is_valid_kind(k: str) -> bool:
    return k in KINDS


def kind_spec(k: str) -> dict:
    if k not in KINDS:
        raise ValueError(f"unknown kind: {k}")
    return KINDS[k]


def pay_url(kind: str, meta: dict) -> Optional[str]:
    return KINDS[kind]["pay_url"](meta or {}) if kind in KINDS else None


def qr_data(kind: str, meta: dict) -> Optional[str]:
    return KINDS[kind]["qr_data"](meta or {}) if kind in KINDS else None


def summary(kind: str, meta: dict) -> str:
    if kind not in KINDS:
        return ""
    try:
        return KINDS[kind]["summary"](meta or {})
    except Exception:
        return ""


# ---------- icons (real brand logos via simpleicons.org CDN) ----------

_SI = "https://cdn.simpleicons.org"

_BRAND_SLUGS = {
    "stripe": "stripe",
    "paypal": "paypal",
    "cashapp": "cashapp",
    "venmo": "venmo",
    "kofi": "kofi",
    "buymeacoffee": "buymeacoffee",
    "zelle": "zelle",
}

# Brand-color pill fallback for kinds with no free logo CDN coverage.
_BRAND_PILLS = {
    "paystack": {"text": "Paystack", "bg": "#011B33", "fg": "#00C3F7"},
}

_CRYPTO_SLUGS = {
    "btc": "bitcoin",
    "eth": "ethereum",
    "sol": "solana",
    "tron": "tether",  # tron is overwhelmingly used for USDT
}

_BANK_SVG = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
    '<polygon points="12 2 21 7 3 7"/><line x1="6" y1="11" x2="6" y2="18"/>'
    '<line x1="10" y1="11" x2="10" y2="18"/><line x1="14" y1="11" x2="14" y2="18"/>'
    '<line x1="18" y1="11" x2="18" y2="18"/><line x1="3" y1="22" x2="21" y2="22"/>'
    '</svg>'
)

_LINK_SVG = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
    '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>'
    '<path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>'
    '</svg>'
)


def kind_icon(kind: str, meta: dict | None = None) -> dict:
    """Returns one of:
      {'type': 'img',  'value': url}
      {'type': 'svg',  'value': svg-markup}
      {'type': 'pill', 'text': str, 'bg': hex, 'fg': hex}
    """
    meta = meta or {}
    if kind == "bank":
        return {"type": "svg", "value": _BANK_SVG}
    if kind == "custom":
        return {"type": "svg", "value": _LINK_SVG}
    if kind == "crypto":
        slug = _CRYPTO_SLUGS.get((meta.get("network") or "").lower(), "bitcoin")
        return {"type": "img", "value": f"{_SI}/{slug}"}
    if kind in _BRAND_PILLS:
        return {"type": "pill", **_BRAND_PILLS[kind]}
    slug = _BRAND_SLUGS.get(kind)
    if slug:
        return {"type": "img", "value": f"{_SI}/{slug}"}
    return {"type": "svg", "value": _LINK_SVG}
