# Changelog

All notable changes to the IRL Python SDK.
Follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) and [Semantic Versioning](https://semver.org/).

---

## [0.3.0] — unreleased

### Changed
- `mta_url` is optional (default `None`). Without it, `authorize()` fetches no heartbeat and sends none, for IRL servers with no regime operator (`MTA_MODE=none`, `LAYER2_ENABLED=false`). Passing an MTA URL works exactly as before. `""` now really disables the fetch, as 0.2.0's notes promised.

### Added
- Retries with exponential backoff on 5xx, `parent_trace_id` trace linking, extended order types, `bind_execution()` / `get_trace()` / `get_trace_chain()` (already in the code and README; first PyPI release with them).

## [0.2.0] — 2026-04-14

### Added
- **Full Layer 2 support** — `IRLClient.authorize()` now automatically fetches, verifies, and attaches a signed Ed25519 MTA heartbeat on every call. No API changes required.
- `mta_url` parameter to `IRLClient` — pass `""` to disable heartbeat fetch (L1 mode or `LAYER2_ENABLED=false`)

### Changed
- Minimum IRL Engine version: 1.1.0 (L2 heartbeat endpoint required)
- `AuthorizeResult.shadow_blocked` field added (reflects engine shadow mode state)

### Fixed
- Heartbeat clock drift edge case — SDK now uses server-reported timestamp rather than local `time.time()` when constructing `agent_valid_time`

---

## [0.1.0] — 2026-03-15

### Added
- `IRLClient` — async context manager wrapping all IRL Engine endpoints
- `client.authorize(AuthorizeRequest)` → `AuthorizeResult`
- `client.bind_execution(BindExecutionRequest)` → `BindExecutionResult`
- `TradeAction` enum: `LONG`, `SHORT`, `NEUTRAL`
- `OrderType` enum: `MARKET`, `LIMIT`, `STOP`, `TWAP`, `VWAP`
- End-to-end demo (`examples/demo_e2e.py`) against the public sandbox
- Full error code documentation

[0.2.0]: https://github.com/norve-labs/irl-sdk-python/releases/tag/v0.2.0
[0.1.0]: https://github.com/norve-labs/irl-sdk-python/releases/tag/v0.1.0
