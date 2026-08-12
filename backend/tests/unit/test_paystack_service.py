"""Unit tests for the Paystack billing client (Increment 7).

No network and no live charge: HTTP is faked with ``httpx.MockTransport`` and the
secret key is a dummy ``sk_test_*`` set per test. These cover the request shape
(amount conversion, currency, auth header), the dormant-until-configured guard,
and the webhook signature check.
"""

import hashlib
import hmac
import json

import httpx
import pytest

from app.config import settings
from app.services import paystack_service as ps


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setattr(settings, "PAYSTACK_SECRET_KEY", "sk_test_dummy")
    monkeypatch.setattr(settings, "PAYSTACK_BASE_URL", "https://api.paystack.co")
    monkeypatch.setattr(settings, "PAYSTACK_CALLBACK_URL", "")


def _mock_transport(monkeypatch, handler):
    """Route the service's httpx.AsyncClient through a MockTransport."""
    real_client = httpx.AsyncClient

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_client(*args, **kwargs)

    monkeypatch.setattr(ps.httpx, "AsyncClient", factory)


def test_kes_to_subunit():
    assert ps.kes_to_subunit(1500) == 150000
    assert ps.kes_to_subunit(0) == 0


def test_verify_webhook_signature_valid_invalid_missing(configured):
    body = b'{"event":"charge.success"}'
    good = hmac.new(b"sk_test_dummy", body, hashlib.sha512).hexdigest()
    assert ps.verify_webhook_signature(body, good) is True
    assert ps.verify_webhook_signature(body, "deadbeef") is False
    assert ps.verify_webhook_signature(body, None) is False


def test_calls_without_key_raise_not_configured(monkeypatch):
    monkeypatch.setattr(settings, "PAYSTACK_SECRET_KEY", "")
    # A signature present but no key configured must fail loudly, not pass.
    with pytest.raises(ps.PaystackNotConfigured):
        ps.verify_webhook_signature(b"x", "sig")


@pytest.mark.asyncio
async def test_initialize_transaction_builds_correct_request(configured, monkeypatch):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["path"] = request.url.path
        captured["auth"] = request.headers.get("authorization")
        captured["json"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "status": True,
                "message": "Authorization URL created",
                "data": {
                    "authorization_url": "https://checkout.paystack.com/abc123",
                    "access_code": "abc123",
                    "reference": "greena_ref_1",
                },
            },
        )

    _mock_transport(monkeypatch, handler)

    data = await ps.initialize_transaction(
        email="farmer@greenafarms.co",
        amount_kes=1500,
        reference="greena_ref_1",
        metadata={"plan": "pro"},
    )

    assert data["authorization_url"] == "https://checkout.paystack.com/abc123"
    assert data["reference"] == "greena_ref_1"
    assert captured["method"] == "POST"
    assert captured["path"] == "/transaction/initialize"
    assert captured["auth"] == "Bearer sk_test_dummy"
    assert captured["json"]["amount"] == 150000  # 1500 KES → cents
    assert captured["json"]["currency"] == "KES"
    assert captured["json"]["metadata"] == {"plan": "pro"}


@pytest.mark.asyncio
async def test_verify_transaction_returns_data(configured, monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/transaction/verify/greena_ref_1"
        return httpx.Response(
            200,
            json={
                "status": True,
                "message": "Verification successful",
                "data": {"status": "success", "amount": 150000, "reference": "greena_ref_1"},
            },
        )

    _mock_transport(monkeypatch, handler)
    data = await ps.verify_transaction("greena_ref_1")
    assert data["status"] == "success"
    assert data["amount"] == 150000


@pytest.mark.asyncio
async def test_api_level_failure_raises(configured, monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": False, "message": "Invalid key"})

    _mock_transport(monkeypatch, handler)
    with pytest.raises(ps.PaystackError, match="Invalid key"):
        await ps.verify_transaction("nope")
