"""
IRLClient — send authorized trade intents to the IRL Engine.

Usage:
    client = IRLClient(
        irl_url="https://irl.macropulse.live",
        api_token="your-token",
        mta_url="https://api.macropulse.live",
    )

    result = await client.authorize(
        AuthorizeRequest(
            agent_id="550e8400-e29b-41d4-a716-446655440000",
            model_id="my-algo-v1",
            model_hash_hex="abc123...",
            action=TradeAction.LONG,
            asset="BTC-USD",
            quantity=0.1,
            notional=6500.0,
        )
    )

    print(result.trace_id, result.authorized)
"""

from __future__ import annotations

import asyncio
import time
from typing import Optional

import httpx

from .models import (
    AuthorizeRequest,
    AuthorizeResult,
    BindExecutionRequest,
    BindExecutionResult,
)


class IRLClient:
    """Async client for the IRL Engine /irl/authorize endpoint.

    Fetches a fresh heartbeat from MacroPulse before each authorize call
    and attaches it automatically. The heartbeat ensures L2 anti-replay
    compliance — do not cache or reuse heartbeats across requests.
    """

    def __init__(
        self,
        irl_url: str,
        api_token: str,
        mta_url: str,
        timeout: float = 5.0,
        max_retries: int = 3,
        backoff_base: float = 0.5,
    ) -> None:
        self._irl_url = irl_url.rstrip("/")
        self._mta_url = mta_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {api_token}"}
        self._http = httpx.AsyncClient(timeout=timeout)
        self._max_retries = max_retries
        self._backoff_base = backoff_base

    async def authorize(self, req: AuthorizeRequest) -> AuthorizeResult:
        """Fetch a fresh heartbeat and submit a trade intent for authorization.

        Raises:
            httpx.HTTPStatusError: on 4xx/5xx from IRL Engine
            RuntimeError: if heartbeat fetch fails
        """
        hb = await self._fetch_heartbeat()

        if req.agent_valid_time == 0:
            req.agent_valid_time = int(time.time() * 1000)

        body = self._build_body(req, hb)

        resp = await self._post_with_retry(f"{self._irl_url}/irl/authorize", json=body)
        resp.raise_for_status()
        data = resp.json()

        return AuthorizeResult(
            trace_id=data["trace_id"],
            reasoning_hash=data["reasoning_hash"],
            authorized=data["authorized"],
            shadow_blocked=data.get("shadow_blocked", False),
        )

    async def bind_execution(self, req: BindExecutionRequest) -> BindExecutionResult:
        """Bind an exchange execution to a previously authorized trace.

        Call after the exchange confirms the order. Computes and stores the
        final_proof that closes the audit chain.

        Raises:
            httpx.HTTPStatusError: on 4xx/5xx from IRL Engine
        """
        resp = await self._post_with_retry(
            f"{self._irl_url}/irl/bind-execution",
            json={
                "trace_id": req.trace_id,
                "exchange_tx_id": req.exchange_tx_id,
                "execution_status": req.execution_status,
                "asset": req.asset,
                "executed_quantity": req.executed_quantity,
                "execution_price": req.execution_price,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return BindExecutionResult(
            final_proof=data["final_proof"],
            status=data["status"],
        )

    async def get_trace(self, trace_id: str) -> dict:
        """Retrieve the full cryptographic trace for forensic replay.

        Raises:
            httpx.HTTPStatusError: on 4xx/5xx (404 if trace not found)
        """
        resp = await self._get_with_retry(f"{self._irl_url}/irl/trace/{trace_id}")
        resp.raise_for_status()
        return resp.json()

    async def get_trace_chain(self, trace_id: str) -> dict:
        """Return the full ancestor chain for a trace (multi-agent audit trail).

        Walks from the given trace up to the root orchestrator, returning
        all ancestor nodes in depth-first order (root first).

        Raises:
            httpx.HTTPStatusError: on 4xx/5xx
        """
        resp = await self._get_with_retry(f"{self._irl_url}/irl/trace/{trace_id}/chain")
        resp.raise_for_status()
        return resp.json()

    async def close(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> "IRLClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    async def _post_with_retry(self, url: str, json: dict) -> httpx.Response:
        """POST with exponential backoff retry on 5xx responses."""
        for attempt in range(self._max_retries + 1):
            resp = await self._http.post(url, json=json, headers=self._headers)
            if resp.status_code < 500 or attempt == self._max_retries:
                return resp
            delay = self._backoff_base * (2 ** attempt)
            await asyncio.sleep(delay)
        return resp  # unreachable; satisfies type checker

    async def _get_with_retry(self, url: str) -> httpx.Response:
        """GET with exponential backoff retry on 5xx responses."""
        for attempt in range(self._max_retries + 1):
            resp = await self._http.get(url, headers=self._headers)
            if resp.status_code < 500 or attempt == self._max_retries:
                return resp
            delay = self._backoff_base * (2 ** attempt)
            await asyncio.sleep(delay)
        return resp

    async def _fetch_heartbeat(self) -> dict:
        resp = await self._http.get(f"{self._mta_url}/v1/irl/heartbeat")
        if resp.status_code != 200:
            raise RuntimeError(
                f"Failed to fetch heartbeat: HTTP {resp.status_code} — {resp.text}"
            )
        return resp.json()

    def _build_body(self, req: AuthorizeRequest, heartbeat: dict) -> dict:
        # Match the AuthorizeRequest JSON schema expected by the IRL Engine.
        # TradeAction variants are serialized as tagged JSON: {"Long": qty}
        action_value: object
        if req.action.value == "Long":
            action_value = {"Long": req.quantity}
        elif req.action.value == "Short":
            action_value = {"Short": req.quantity}
        elif req.action.value == "Neutral":
            action_value = "Neutral"
        else:
            action_value = req.action.value

        body: dict = {
            "agent_id": req.agent_id,
            "model_id": req.model_id,
            "model_hash_hex": req.model_hash_hex,
            "prompt_version": req.prompt_version,
            "feature_schema_id": req.feature_schema_id,
            "hyperparameter_checksum": req.hyperparameter_checksum,
            "action": action_value,
            "asset": req.asset,
            "order_type": req.order_type.value,
            "venue_id": req.venue_id,
            "quantity": req.quantity,
            "notional": req.notional,
            "notional_currency": req.notional_currency,
            "multiplier": req.multiplier,
            "reduce_only": req.reduce_only,
            "agent_valid_time": req.agent_valid_time,
            "heartbeat": heartbeat,
        }

        body["client_order_id"] = req.client_order_id or ""

        if req.limit_price is not None:
            body["limit_price"] = req.limit_price
        if req.stop_price is not None:
            body["stop_price"] = req.stop_price
        if req.regulatory is not None:
            body["regulatory"] = req.regulatory
        if req.parent_trace_id is not None:
            body["parent_trace_id"] = req.parent_trace_id

        return body
