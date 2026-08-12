"""
Greena — Paystack billing client.

A thin async wrapper over the Paystack REST API for subscription payments.
Backend-only: the secret key authenticates server→Paystack calls and is never
exposed to the client. The service is **dormant until PAYSTACK_SECRET_KEY is
set** — every call raises ``PaystackNotConfigured`` otherwise, so a missing key
fails loudly instead of silently pretending a charge succeeded.

Local verification uses Paystack **test** keys or mocked HTTP; a test never
issues a live charge.

Scope (Increment 7): the client only. Persistence, endpoints, and paywall
wiring land in later increments.
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Any

import httpx

from app.config import settings


class PaystackError(Exception):
    """A Paystack API call failed or returned an unsuccessful status."""


class PaystackNotConfigured(PaystackError):
    """PAYSTACK_SECRET_KEY is unset — billing is not configured."""


def _secret() -> str:
    key = settings.PAYSTACK_SECRET_KEY
    if not key:
        raise PaystackNotConfigured("PAYSTACK_SECRET_KEY is not set")
    return key


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_secret()}",
        "Content-Type": "application/json",
    }


def kes_to_subunit(amount_kes: int) -> int:
    """Paystack charges in the currency subunit; KES is expressed in cents."""
    return int(amount_kes) * 100


async def initialize_transaction(
    *,
    email: str,
    amount_kes: int,
    reference: str,
    callback_url: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a Paystack transaction.

    Returns Paystack's ``data`` object — notably ``authorization_url`` (where the
    customer completes payment), ``access_code``, and the echoed ``reference``.
    """
    payload: dict[str, Any] = {
        "email": email,
        "amount": kes_to_subunit(amount_kes),
        "currency": "KES",
        "reference": reference,
    }
    cb = callback_url or settings.PAYSTACK_CALLBACK_URL
    if cb:
        payload["callback_url"] = cb
    if metadata:
        payload["metadata"] = metadata
    return await _post("/transaction/initialize", payload)


async def verify_transaction(reference: str) -> dict[str, Any]:
    """Fetch a transaction's authoritative state from Paystack.

    The returned ``data`` includes ``status`` ('success' | 'failed' | …),
    ``amount`` (subunit), ``currency``, ``reference``, and ``metadata``. This is
    the source of truth — never trust a client-reported payment result.
    """
    return await _get(f"/transaction/verify/{reference}")


def verify_webhook_signature(raw_body: bytes, signature: str | None) -> bool:
    """Validate an incoming Paystack webhook.

    Paystack signs the **raw request body** with HMAC-SHA512 keyed by the
    secret key and sends the hex digest in the ``X-Paystack-Signature`` header.
    Compared in constant time. Returns False on a missing/short signature.
    """
    if not signature:
        return False
    computed = hmac.new(_secret().encode(), raw_body, hashlib.sha512).hexdigest()
    return hmac.compare_digest(computed, signature)


# ── HTTP plumbing ─────────────────────────────────────────────────────────────

async def _post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    async with httpx.AsyncClient(base_url=settings.PAYSTACK_BASE_URL, timeout=20) as client:
        resp = await client.post(path, json=payload, headers=_headers())
    return _unwrap(resp)


async def _get(path: str) -> dict[str, Any]:
    async with httpx.AsyncClient(base_url=settings.PAYSTACK_BASE_URL, timeout=20) as client:
        resp = await client.get(path, headers=_headers())
    return _unwrap(resp)


def _unwrap(resp: httpx.Response) -> dict[str, Any]:
    """Paystack wraps every response as ``{status: bool, message, data}``.

    Treat both a transport error (HTTP ≥ 400) and an application-level
    ``status: false`` as failures.
    """
    try:
        body = resp.json()
    except Exception as exc:  # noqa: BLE001 — surface any non-JSON as a clean error
        raise PaystackError(
            f"Paystack returned a non-JSON response (HTTP {resp.status_code})"
        ) from exc
    if resp.status_code >= 400 or not body.get("status", False):
        raise PaystackError(f"Paystack error: {body.get('message', f'HTTP {resp.status_code}')}")
    return body.get("data", {})
