import asyncio
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi import HTTPException
from invite_access import require_invited_user


def check(response):
    client = AsyncMock()
    client.get.return_value = response
    with patch("invite_access.httpx.AsyncClient") as factory:
        factory.return_value.__aenter__.return_value = client
        asyncio.run(require_invited_user("https://example.convex.site", "test-token"))
    client.get.assert_awaited_once_with("https://example.convex.site/api/daisy/access", headers={"Authorization": "Bearer test-token"})


def reply(status, data):
    return httpx.Response(status, json=data, request=httpx.Request("GET", "https://example.convex.site/api/daisy/access"))


def test_approved_account_is_allowed():
    check(reply(200, {"approved": True}))


@pytest.mark.parametrize("data", [{"approved": False}, {"approved": "true"}, {}, [], {"approved": 1}])
def test_pending_revoked_and_malformed_responses_fail_closed(data):
    with pytest.raises(HTTPException) as error:
        check(reply(200, data))
    assert error.value.status_code == (403 if data == {"approved": False} else 503)


@pytest.mark.parametrize("status,expected", [(401, 401), (404, 503), (500, 503)])
def test_expired_tokens_missing_gate_and_outages_block_access(status, expected):
    with pytest.raises(HTTPException) as error:
        check(reply(status, {}))
    assert error.value.status_code == expected


def test_network_outage_does_not_grant_access():
    client = AsyncMock()
    client.get.side_effect = httpx.ConnectError("unavailable")
    with patch("invite_access.httpx.AsyncClient") as factory:
        factory.return_value.__aenter__.return_value = client
        with pytest.raises(HTTPException) as error:
            asyncio.run(require_invited_user("https://example.convex.site", "token"))
    assert error.value.status_code == 503


def test_valid_jwt_still_requires_live_approval():
    import main
    from types import SimpleNamespace
    with (patch.object(main, "AUTH_PROVIDER", "convex"),
          patch.object(main, "CONVEX_SITE_URL", "https://example.convex.site"),
          patch.object(main, "CONVEX_JWKS") as jwks,
          patch.object(main.jwt, "decode", return_value={"sub": "member", "email": "member@example.invalid"}),
          patch.object(main, "require_invited_user", new_callable=AsyncMock) as approval):
        jwks.get_signing_key_from_jwt.return_value = SimpleNamespace(key="test-key")
        approval.side_effect = HTTPException(status_code=403, detail="Approval required")
        with pytest.raises(HTTPException) as error:
            asyncio.run(main.validate_access_token("valid-token"))
        assert error.value.status_code == 403
        approval.assert_awaited_once_with("https://example.convex.site", "valid-token")
        approval.side_effect = None
        result = asyncio.run(main.validate_access_token("valid-token"))
        assert result["id"] == "member"
