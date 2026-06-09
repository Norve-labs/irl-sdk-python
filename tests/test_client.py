"""Tests for IRLClient — mirror of the TypeScript SDK vitest suite."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from irl_sdk import (
    AuthorizeRequest,
    AuthorizeResult,
    BindExecutionRequest,
    BindExecutionResult,
    IRLClient,
    OrderType,
    TradeAction,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FAKE_HEARTBEAT = {
    "sequence_id": 42,
    "timestamp_ms": 1_700_000_000_000,
    "regime_id": 2,
    "mta_ref": "0xmockref",
    "signature": "AAAA",
}

FAKE_AUTHORIZE_RESPONSE = {
    "trace_id": "550e8400-e29b-41d4-a716-446655440000",
    "reasoning_hash": "abc123" + "0" * 58,
    "authorized": True,
    "shadow_blocked": False,
}

FAKE_BIND_RESPONSE = {
    "final_proof": "proof_" + "x" * 60,
    "status": "MATCHED",
}

FAKE_TRACE = {
    "trace_id": "550e8400-e29b-41d4-a716-446655440000",
    "integrity": {"reasoning_hash": "abc123", "verification_status": "MATCHED"},
}

FAKE_CHAIN = {
    "trace_id": "550e8400-e29b-41d4-a716-446655440000",
    "chain": [{"trace_id": "parent-uuid", "depth": 0}],
}

BASE_REQ = dict(
    agent_id="550e8400-e29b-41d4-a716-446655440000",
    model_id="test-model-v1",
    model_hash_hex="a" * 64,
    asset="BTC-USD",
    venue_id="CBSE",
    quantity=0.1,
    notional=6500.0,
)


def _make_response(status: int, body: dict) -> httpx.Response:
    return httpx.Response(status, json=body, request=httpx.Request("GET", "http://test"))


def _make_client() -> IRLClient:
    return IRLClient(
        irl_url="http://irl.test",
        api_token="test-token",
        mta_url="http://mta.test",
    )


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------


def test_order_type_enum_has_vwap_ioc_fok():
    assert OrderType.VWAP == "VWAP"
    assert OrderType.IOC == "IOC"
    assert OrderType.FOK == "FOK"
    assert OrderType.POST_ONLY == "POST_ONLY"
    assert OrderType.TRAILING_STOP == "TRAILING_STOP"


def test_authorize_request_parent_trace_id_defaults_none():
    req = AuthorizeRequest(agent_id="a", model_id="m", model_hash_hex="b" * 64)
    assert req.parent_trace_id is None


def test_bind_execution_result_fields():
    r = BindExecutionResult(final_proof="fp", status="MATCHED")
    assert r.final_proof == "fp"
    assert r.status == "MATCHED"


# ---------------------------------------------------------------------------
# IRLClient.authorize
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_authorize_returns_authorize_result():
    client = _make_client()
    with (
        patch.object(client, "_fetch_heartbeat", new=AsyncMock(return_value=FAKE_HEARTBEAT)),
        patch.object(
            client._http,
            "post",
            new=AsyncMock(return_value=_make_response(200, FAKE_AUTHORIZE_RESPONSE)),
        ),
    ):
        result = await client.authorize(AuthorizeRequest(**BASE_REQ))

    assert isinstance(result, AuthorizeResult)
    assert result.trace_id == FAKE_AUTHORIZE_RESPONSE["trace_id"]
    assert result.authorized is True
    assert result.shadow_blocked is False
    await client.close()


@pytest.mark.asyncio
async def test_authorize_includes_parent_trace_id_when_set():
    client = _make_client()
    req = AuthorizeRequest(**BASE_REQ, parent_trace_id="parent-uuid-0000")
    captured: list[dict] = []

    async def mock_post(url: str, *, json: dict, headers: dict) -> httpx.Response:
        captured.append(json)
        return _make_response(200, FAKE_AUTHORIZE_RESPONSE)

    with (
        patch.object(client, "_fetch_heartbeat", new=AsyncMock(return_value=FAKE_HEARTBEAT)),
        patch.object(client._http, "post", new=AsyncMock(side_effect=mock_post)),
    ):
        await client.authorize(req)

    assert captured[0]["parent_trace_id"] == "parent-uuid-0000"
    await client.close()


@pytest.mark.asyncio
async def test_authorize_raises_on_4xx():
    client = _make_client()

    error_resp = httpx.Response(
        403,
        json={"error": "REGIME_VIOLATION"},
        request=httpx.Request("POST", "http://test"),
    )

    with (
        patch.object(client, "_fetch_heartbeat", new=AsyncMock(return_value=FAKE_HEARTBEAT)),
        patch.object(
            client._http,
            "post",
            new=AsyncMock(return_value=error_resp),
        ),
    ):
        with pytest.raises(httpx.HTTPStatusError):
            await client.authorize(AuthorizeRequest(**BASE_REQ))

    await client.close()


# ---------------------------------------------------------------------------
# IRLClient.bind_execution
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bind_execution_returns_result():
    client = _make_client()
    req = BindExecutionRequest(
        trace_id="550e8400-e29b-41d4-a716-446655440000",
        exchange_tx_id="EXCH-TX-001",
        execution_status="Filled",
        asset="BTC-USD",
        executed_quantity=0.1,
        execution_price=65_000.0,
    )
    with patch.object(
        client._http,
        "post",
        new=AsyncMock(return_value=_make_response(200, FAKE_BIND_RESPONSE)),
    ):
        result = await client.bind_execution(req)

    assert isinstance(result, BindExecutionResult)
    assert result.status == "MATCHED"
    assert result.final_proof.startswith("proof_")
    await client.close()


# ---------------------------------------------------------------------------
# IRLClient.get_trace
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_trace_returns_dict():
    client = _make_client()
    with patch.object(
        client._http,
        "get",
        new=AsyncMock(return_value=_make_response(200, FAKE_TRACE)),
    ):
        trace = await client.get_trace("550e8400-e29b-41d4-a716-446655440000")

    assert trace["trace_id"] == FAKE_TRACE["trace_id"]
    await client.close()


@pytest.mark.asyncio
async def test_get_trace_raises_on_404():
    client = _make_client()
    not_found = httpx.Response(
        404,
        json={"error": "NOT_FOUND"},
        request=httpx.Request("GET", "http://test"),
    )
    with patch.object(client._http, "get", new=AsyncMock(return_value=not_found)):
        with pytest.raises(httpx.HTTPStatusError):
            await client.get_trace("nonexistent")
    await client.close()


# ---------------------------------------------------------------------------
# IRLClient.get_trace_chain
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_trace_chain_returns_chain():
    client = _make_client()
    with patch.object(
        client._http,
        "get",
        new=AsyncMock(return_value=_make_response(200, FAKE_CHAIN)),
    ):
        chain = await client.get_trace_chain("550e8400-e29b-41d4-a716-446655440000")

    assert "chain" in chain
    assert len(chain["chain"]) == 1
    await client.close()


# ---------------------------------------------------------------------------
# Context manager
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_context_manager_closes_client():
    async with _make_client() as client:
        assert client is not None
