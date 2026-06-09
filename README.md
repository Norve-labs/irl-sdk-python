# irl-sdk — Python SDK for the IRL Engine

[![PyPI version](https://img.shields.io/badge/pypi-0.3.0-blue)](https://pypi.org/project/irl-sdk/)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://pypi.org/project/irl-sdk/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![IRL Engine](https://img.shields.io/badge/IRL%20Engine-v1.2.0%20compatible-brightgreen)](https://github.com/GabrielGauss/IRL-engine-AX)

Async Python client for the [IRL Engine](https://irl.macropulse.live) — the cryptographic
pre-execution compliance gateway for autonomous AI trading agents.

- Fetches a signed Layer 2 heartbeat from the MTA operator automatically
- Constructs and signs the authorize request
- Returns a sealed `trace_id` and `reasoning_hash` before any order reaches the exchange

## What's new in 0.3.0

- **Retry + circuit breaker**: All API calls retry on 5xx responses with exponential backoff (default: 3 retries, 0.5 s base delay). Configurable via `max_retries` and `backoff_base`.
- **Multi-agent trace linking**: `AuthorizeRequest.parent_trace_id` links a sub-agent call to its orchestrator, enabling full causal chain audits via `get_trace_chain()`.
- **Extended order types**: `OrderType` now includes `VWAP`, `IOC`, `FOK`, `POST_ONLY`, `PEGGED`, `TRAILING_STOP`, `ICEBERG`.
- **`bind_execution()` + `get_trace()` + `get_trace_chain()`**: Full post-trade and audit chain methods.

## Install

```bash
pip install irl-sdk
```

Requires Python 3.10+.

## Quick Start

```python
import asyncio
from irl_sdk import IRLClient, AuthorizeRequest, TradeAction, OrderType

IRL_URL   = "https://irl.macropulse.live"
MTA_URL   = "https://api.macropulse.live"
API_TOKEN = "your-irl-api-token"
AGENT_ID  = "your-agent-uuid"           # from POST /irl/agents
MODEL_HASH = "your-model-sha256-hex"    # 64-char hex

async def main():
    async with IRLClient(IRL_URL, API_TOKEN, MTA_URL) as client:
        req = AuthorizeRequest(
            agent_id=AGENT_ID,
            model_id="my-model-v1",
            model_hash_hex=MODEL_HASH,
            action=TradeAction.LONG,
            asset="BTC-USD",
            order_type=OrderType.MARKET,
            venue_id="coinbase",
            quantity=0.1,
            notional=6500.0,
            notional_currency="USD",
        )
        result = await client.authorize(req)

        if result.authorized:
            print(f"AUTHORIZED  trace_id={result.trace_id}")
            print(f"reasoning_hash={result.reasoning_hash[:24]}...")
            # embed trace_id in your exchange order metadata, then place the order
        else:
            print("HALTED — IRL blocked the trade")

asyncio.run(main())
```

## End-to-End Demo

The demo registers nothing — it uses a pre-seeded demo agent in the public sandbox:

```bash
cd examples
pip install -e ..
python demo_e2e.py
```

Expected output:
```
IRL Engine : https://irl.macropulse.live
MTA        : https://api.macropulse.live
Agent ID   : 00000000-0000-4000-a000-000000000001

Fetching heartbeat and submitting authorize request...

AUTHORIZED
  trace_id      : <uuid>
  reasoning_hash: <first 24 chars>...
  shadow_blocked: False
```

## API Reference

### `IRLClient(irl_url, api_token, mta_url, timeout, max_retries, backoff_base)`

Async context manager. All parameters are positional.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `irl_url` | str | — | IRL Engine base URL |
| `api_token` | str | — | Bearer token (from `IRL_API_TOKENS` env on the engine) |
| `mta_url` | str | — | MTA operator URL for heartbeat fetch. Pass empty string `""` when `LAYER2_ENABLED=false`. |
| `timeout` | float | `5.0` | HTTP request timeout in seconds |
| `max_retries` | int | `3` | Max retry attempts on 5xx responses |
| `backoff_base` | float | `0.5` | Base delay (seconds) for exponential backoff between retries |

### `client.authorize(req: AuthorizeRequest) → AuthorizeResult`

1. Fetches a fresh signed heartbeat from `{mta_url}/v1/irl/heartbeat`
2. POSTs to `{irl_url}/irl/authorize` with the heartbeat and request payload
3. Returns `AuthorizeResult`

### `AuthorizeRequest` fields

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `agent_id` | str | yes | UUID registered via `POST /irl/agents` |
| `model_id` | str | yes | Human-readable model name |
| `model_hash_hex` | str | yes | SHA-256 of model config (64 hex chars) |
| `action` | TradeAction | yes | `LONG` / `SHORT` / `NEUTRAL` |
| `asset` | str | yes | e.g. `"BTC-USD"`, `"SPY"` |
| `order_type` | OrderType | yes | `MARKET` / `LIMIT` / `STOP` / `TWAP` / `VWAP` |
| `venue_id` | str | yes | Exchange identifier |
| `quantity` | float | yes | Order size |
| `notional` | float | yes | Notional value |
| `notional_currency` | str | yes | e.g. `"USD"` |
| `client_order_id` | str | no | Your internal order reference |
| `agent_valid_time` | int | no | Model inference timestamp (ms). Defaults to now. |
| `parent_trace_id` | str | no | `trace_id` of the orchestrator decision that triggered this sub-agent call. Enables `get_trace_chain()` causal audits. |

### `AuthorizeResult` fields

| Field | Type | Notes |
|-------|------|-------|
| `trace_id` | str | UUID — embed in exchange order metadata |
| `reasoning_hash` | str | SHA-256 seal of the full cognitive snapshot |
| `authorized` | bool | `True` = proceed; `False` = halted by policy |
| `shadow_blocked` | bool | `True` = would have been blocked; only set when `SHADOW_MODE=true` on the engine |

### `TradeAction`

```python
from irl_sdk import TradeAction

TradeAction.LONG     # "Long"
TradeAction.SHORT    # "Short"
TradeAction.NEUTRAL  # "Neutral"
```

### `OrderType`

```python
from irl_sdk import OrderType

OrderType.MARKET        # "MARKET"
OrderType.LIMIT         # "LIMIT"
OrderType.STOP          # "STOP"
OrderType.TWAP          # "TWAP"
OrderType.VWAP          # "VWAP"
OrderType.IOC           # "IOC"
OrderType.FOK           # "FOK"
OrderType.POST_ONLY     # "POST_ONLY"
OrderType.PEGGED        # "PEGGED"
OrderType.TRAILING_STOP # "TRAILING_STOP"
OrderType.ICEBERG       # "ICEBERG"
```

### `client.get_trace_chain(trace_id: str) → dict`

Returns the full causal ancestry chain for a trace. Useful for multi-agent audit trails where sub-agent decisions trace back to an orchestrator.

```python
chain = await client.get_trace_chain(result.trace_id)
# {"trace_id": "...", "ancestry": [...], "children": [...]}
```

## Error Handling

The SDK raises `httpx.HTTPStatusError` on non-2xx responses. The response body
contains `{"error": "ERROR_CODE", "message": "..."}`. Common codes:

| Code | Meaning |
|------|---------|
| `HEARTBEAT_DRIFT_EXCEEDED` | Heartbeat too old — clock skew or slow network |
| `HEARTBEAT_MTA_REF_MISMATCH` | MTA hash mismatch — regime changed between heartbeat and authorize |
| `REGIME_VIOLATION` | Action not permitted in current regime |
| `NOTIONAL_EXCEEDS_LIMIT` | Exceeds agent notional cap × regime scale |
| `MODEL_HASH_MISMATCH` | Provided hash ≠ registered hash |
| `AGENT_NOT_FOUND` | Register the agent first via `POST /irl/agents` |

## Layer 2 (Heartbeat) Details

When `LAYER2_ENABLED=true` on the engine (default), every authorize request must
carry a `SignedHeartbeat`. The SDK fetches this automatically from `{mta_url}/v1/irl/heartbeat`.

The heartbeat binds each request to a specific MTA broadcast:
- `sequence_id` — strictly monotone (anti-replay)
- `timestamp_ms` — must be within `MAX_HEARTBEAT_DRIFT_MS` of `txn_time`
- `mta_ref` — SHA-256 of the raw `/v1/regime/current` HTTP response body
- `signature` — Ed25519 signature by the MTA operator

For local dev with `LAYER2_ENABLED=false`, pass `mta_url=""`. The engine
substitutes a zero heartbeat internally.

---

## Ecosystem

| Repo | Description |
|---|---|
| [IRL-engine-AX](https://github.com/GabrielGauss/IRL-engine-AX) | Core IRL Engine |
| [irl-sdk-ts](https://github.com/GabrielGauss/irl-sdk-ts) | TypeScript/Node.js SDK |
| [irl-public-docs](https://github.com/GabrielGauss/irl-public-docs) | Public documentation hub |
| [macropulse](https://github.com/GabrielGauss/macropulse) | MacroPulse — MTA operator |

## License

MIT
