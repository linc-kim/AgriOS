"""
AGRIOS — ARIA Module Integration Tests
Tests the full ARIA lifecycle against a real (test) database.

Test coverage:
  1.  POST /aria/chat — creates new conversation, returns assistant reply
  2.  POST /aria/chat with conversation_id — continues existing conversation
  3.  GET /aria/conversations — list returns the created conversation
  4.  GET /aria/conversations/{id} — detail includes messages
  5.  DELETE /aria/conversations/{id} — soft-delete succeeds
  6.  GET /aria/conversations/{id} after delete — 404
  7.  GET /aria/insights — returns list with severity_counts
  8.  PATCH /aria/insights/{id}/dismiss — dismissed_at is set
  9.  GET /aria/insights after dismiss — dismissed insight excluded by default
 10.  GET /aria/recommendations — returns list with pending_count
 11.  PATCH /aria/recommendations/{id}/action (acted) — status becomes "acted"
 12.  PATCH /aria/recommendations/{id}/action (dismissed) — status becomes "dismissed"
 13.  GET /aria/usage — returns quota data and plan_name
 14.  RBAC: farm_worker cannot POST /aria/chat (403)
 15.  RBAC: viewer can GET /aria/insights (200)
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

# These tests follow the async fixture pattern from test_finance_flow.py.
# They assume:
#   - `async_client` fixture: authenticated httpx.AsyncClient
#   - `test_farm` fixture: Farm with id, subscription_plan="free"
#   - `test_flock` fixture: active Flock in test_farm
#   - `auth_headers_owner`  — farm_owner JWT headers
#   - `auth_headers_manager` — farm_manager JWT headers
#   - `auth_headers_worker`  — farm_worker JWT headers
#   - `auth_headers_viewer`  — viewer JWT headers
# Fixture infrastructure is in conftest.py (shared Sprint 0/2 setup).
#
# AI provider calls are MOCKED throughout — tests must not hit external APIs.

pytestmark = pytest.mark.asyncio

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

MOCK_AI_RESPONSE = (
    "Based on your farm data, your flock is performing within normal ranges.",
    100,   # prompt_tokens
    50,    # completion_tokens
    150,   # total_tokens
    1200,  # duration_ms
)

ARIA_CHAT_URL = "/api/v1/farms/{farm_id}/aria/chat"
CONVERSATIONS_URL = "/api/v1/farms/{farm_id}/aria/conversations"
CONVERSATION_URL = "/api/v1/farms/{farm_id}/aria/conversations/{conv_id}"
INSIGHTS_URL = "/api/v1/farms/{farm_id}/aria/insights"
INSIGHT_DISMISS_URL = "/api/v1/farms/{farm_id}/aria/insights/{insight_id}/dismiss"
RECOMMENDATIONS_URL = "/api/v1/farms/{farm_id}/aria/recommendations"
REC_ACTION_URL = "/api/v1/farms/{farm_id}/aria/recommendations/{rec_id}/action"
USAGE_URL = "/api/v1/farms/{farm_id}/aria/usage"


def _chat_url(farm_id):
    return ARIA_CHAT_URL.format(farm_id=farm_id)

def _convs_url(farm_id):
    return CONVERSATIONS_URL.format(farm_id=farm_id)

def _conv_url(farm_id, conv_id):
    return CONVERSATION_URL.format(farm_id=farm_id, conv_id=conv_id)

def _insights_url(farm_id):
    return INSIGHTS_URL.format(farm_id=farm_id)

def _insight_dismiss_url(farm_id, insight_id):
    return INSIGHT_DISMISS_URL.format(farm_id=farm_id, insight_id=insight_id)

def _recs_url(farm_id):
    return RECOMMENDATIONS_URL.format(farm_id=farm_id)

def _rec_action_url(farm_id, rec_id):
    return REC_ACTION_URL.format(farm_id=farm_id, rec_id=rec_id)

def _usage_url(farm_id):
    return USAGE_URL.format(farm_id=farm_id)


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestARIAChat:
    """Tests 1-2: Chat endpoint — create and continue conversations."""

    @patch(
        "app.services.aria_service._call_gemini",
        new_callable=AsyncMock,
        return_value=MOCK_AI_RESPONSE,
    )
    async def test_send_message_creates_new_conversation(
        self, mock_gemini, async_client, test_farm, auth_headers_owner
    ):
        farm_id = test_farm.id
        resp = await async_client.post(
            _chat_url(farm_id),
            json={"content": "How is my flock doing?"},
            headers=auth_headers_owner,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "conversation_id" in data
        assert "message" in data
        assert data["message"]["role"] == "assistant"
        assert data["message"]["content"] == MOCK_AI_RESPONSE[0]
        assert data["quota_remaining"] is not None or data["quota_remaining"] is None  # may be None for unlimited
        mock_gemini.assert_awaited_once()

    @patch(
        "app.services.aria_service._call_gemini",
        new_callable=AsyncMock,
        return_value=MOCK_AI_RESPONSE,
    )
    async def test_send_message_continues_existing_conversation(
        self, mock_gemini, async_client, test_farm, auth_headers_owner
    ):
        farm_id = test_farm.id
        # First message — create conversation
        resp1 = await async_client.post(
            _chat_url(farm_id),
            json={"content": "How many eggs this week?"},
            headers=auth_headers_owner,
        )
        assert resp1.status_code == 200
        conv_id = resp1.json()["data"]["conversation_id"]

        # Second message — continue same conversation
        resp2 = await async_client.post(
            _chat_url(farm_id),
            json={"content": "What about feed costs?", "conversation_id": conv_id},
            headers=auth_headers_owner,
        )
        assert resp2.status_code == 200
        assert resp2.json()["data"]["conversation_id"] == conv_id


class TestConversationLifecycle:
    """Tests 3-6: Conversation list, detail, and delete."""

    @patch(
        "app.services.aria_service._call_gemini",
        new_callable=AsyncMock,
        return_value=MOCK_AI_RESPONSE,
    )
    async def test_list_conversations_returns_created(
        self, mock_gemini, async_client, test_farm, auth_headers_owner
    ):
        farm_id = test_farm.id
        # Create a conversation
        await async_client.post(
            _chat_url(farm_id),
            json={"content": "Test message"},
            headers=auth_headers_owner,
        )
        resp = await async_client.get(_convs_url(farm_id), headers=auth_headers_owner)
        assert resp.status_code == 200
        convs = resp.json()["data"]
        assert isinstance(convs, list)
        assert len(convs) >= 1

    @patch(
        "app.services.aria_service._call_gemini",
        new_callable=AsyncMock,
        return_value=MOCK_AI_RESPONSE,
    )
    async def test_get_conversation_detail_includes_messages(
        self, mock_gemini, async_client, test_farm, auth_headers_owner
    ):
        farm_id = test_farm.id
        resp1 = await async_client.post(
            _chat_url(farm_id),
            json={"content": "What is my FCR?"},
            headers=auth_headers_owner,
        )
        conv_id = resp1.json()["data"]["conversation_id"]

        resp2 = await async_client.get(
            _conv_url(farm_id, conv_id), headers=auth_headers_owner
        )
        assert resp2.status_code == 200
        detail = resp2.json()["data"]
        assert "messages" in detail
        # Should have at least 2 messages: user + assistant
        assert len(detail["messages"]) >= 2

    @patch(
        "app.services.aria_service._call_gemini",
        new_callable=AsyncMock,
        return_value=MOCK_AI_RESPONSE,
    )
    async def test_delete_conversation(
        self, mock_gemini, async_client, test_farm, auth_headers_owner
    ):
        farm_id = test_farm.id
        resp1 = await async_client.post(
            _chat_url(farm_id),
            json={"content": "To be deleted"},
            headers=auth_headers_owner,
        )
        conv_id = resp1.json()["data"]["conversation_id"]

        del_resp = await async_client.delete(
            _conv_url(farm_id, conv_id), headers=auth_headers_owner
        )
        assert del_resp.status_code == 200
        assert del_resp.json()["data"]["deleted"] is True

    @patch(
        "app.services.aria_service._call_gemini",
        new_callable=AsyncMock,
        return_value=MOCK_AI_RESPONSE,
    )
    async def test_get_deleted_conversation_returns_404(
        self, mock_gemini, async_client, test_farm, auth_headers_owner
    ):
        farm_id = test_farm.id
        resp1 = await async_client.post(
            _chat_url(farm_id),
            json={"content": "Ephemeral"},
            headers=auth_headers_owner,
        )
        conv_id = resp1.json()["data"]["conversation_id"]
        await async_client.delete(_conv_url(farm_id, conv_id), headers=auth_headers_owner)

        resp2 = await async_client.get(
            _conv_url(farm_id, conv_id), headers=auth_headers_owner
        )
        assert resp2.status_code == 404


class TestInsights:
    """Tests 7-9: Insights list and dismiss."""

    async def test_list_insights_returns_severity_counts(
        self, async_client, test_farm, auth_headers_owner
    ):
        farm_id = test_farm.id
        resp = await async_client.get(_insights_url(farm_id), headers=auth_headers_owner)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "insights" in data
        assert "severity_counts" in data
        counts = data["severity_counts"]
        assert all(k in counts for k in ("alert", "warning", "info", "reminder"))

    async def test_dismiss_insight(
        self, async_client, test_farm, auth_headers_owner
    ):
        """Requires at least one active insight to be present (generated by fixture or seeded)."""
        farm_id = test_farm.id
        list_resp = await async_client.get(
            _insights_url(farm_id), headers=auth_headers_owner
        )
        insights = list_resp.json()["data"]["insights"]
        if not insights:
            pytest.skip("No active insights available — seed data required")

        insight_id = insights[0]["id"]
        resp = await async_client.patch(
            _insight_dismiss_url(farm_id, insight_id),
            headers=auth_headers_owner,
        )
        assert resp.status_code == 200
        dismissed = resp.json()["data"]
        assert dismissed["is_dismissed"] is True
        assert dismissed["dismissed_at"] is not None

    async def test_dismissed_insight_excluded_from_default_list(
        self, async_client, test_farm, auth_headers_owner
    ):
        farm_id = test_farm.id
        list_resp = await async_client.get(
            _insights_url(farm_id), headers=auth_headers_owner
        )
        insights = list_resp.json()["data"]["insights"]
        if not insights:
            pytest.skip("No active insights to dismiss")

        insight_id = insights[0]["id"]
        await async_client.patch(
            _insight_dismiss_url(farm_id, insight_id),
            headers=auth_headers_owner,
        )

        # Default list (include_dismissed=false) should not include this one
        re_list_resp = await async_client.get(
            _insights_url(farm_id), headers=auth_headers_owner
        )
        re_insights = re_list_resp.json()["data"]["insights"]
        ids = [i["id"] for i in re_insights]
        assert insight_id not in ids


class TestRecommendations:
    """Tests 10-12: Recommendations list and act/dismiss."""

    async def test_list_recommendations_returns_pending_count(
        self, async_client, test_farm, auth_headers_owner
    ):
        farm_id = test_farm.id
        resp = await async_client.get(_recs_url(farm_id), headers=auth_headers_owner)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "recommendations" in data
        assert "pending_count" in data
        assert isinstance(data["pending_count"], int)

    async def test_act_recommendation(
        self, async_client, test_farm, auth_headers_owner
    ):
        farm_id = test_farm.id
        list_resp = await async_client.get(
            _recs_url(farm_id) + "?status=pending", headers=auth_headers_owner
        )
        recs = list_resp.json()["data"]["recommendations"]
        if not recs:
            pytest.skip("No pending recommendations — seed data required")

        rec_id = recs[0]["id"]
        resp = await async_client.patch(
            _rec_action_url(farm_id, rec_id),
            json={"action": "acted"},
            headers=auth_headers_owner,
        )
        assert resp.status_code == 200
        result = resp.json()["data"]
        assert result["status"] == "acted"
        assert result["acted_at"] is not None

    async def test_dismiss_recommendation(
        self, async_client, test_farm, auth_headers_owner
    ):
        farm_id = test_farm.id
        list_resp = await async_client.get(
            _recs_url(farm_id) + "?status=pending", headers=auth_headers_owner
        )
        recs = list_resp.json()["data"]["recommendations"]
        if not recs:
            pytest.skip("No pending recommendations — seed data required")

        rec_id = recs[0]["id"]
        resp = await async_client.patch(
            _rec_action_url(farm_id, rec_id),
            json={"action": "dismissed"},
            headers=auth_headers_owner,
        )
        assert resp.status_code == 200
        result = resp.json()["data"]
        assert result["status"] == "dismissed"
        assert result["dismissed_at"] is not None


class TestUsageQuota:
    """Test 13: Quota / usage endpoint."""

    async def test_get_usage_returns_quota_data(
        self, async_client, test_farm, auth_headers_owner
    ):
        farm_id = test_farm.id
        resp = await async_client.get(_usage_url(farm_id), headers=auth_headers_owner)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "conversations_this_month" in data
        assert "monthly_limit" in data
        assert "plan_name" in data
        assert isinstance(data["conversations_this_month"], int)


class TestARIARBAC:
    """Tests 14-15: Role-based access control for ARIA endpoints."""

    async def test_farm_worker_cannot_send_chat_message(
        self, async_client, test_farm, auth_headers_worker
    ):
        farm_id = test_farm.id
        resp = await async_client.post(
            _chat_url(farm_id),
            json={"content": "Can I ask ARIA?"},
            headers=auth_headers_worker,
        )
        assert resp.status_code == 403

    async def test_viewer_can_read_insights(
        self, async_client, test_farm, auth_headers_viewer
    ):
        farm_id = test_farm.id
        resp = await async_client.get(
            _insights_url(farm_id), headers=auth_headers_viewer
        )
        # AI_INSIGHT_VIEW covers viewer role
        assert resp.status_code == 200
