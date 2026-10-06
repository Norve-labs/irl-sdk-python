"""
IRL SDK — end-to-end demo.

Registers an agent in the IRL Engine MAR (if not already present) and
submits a test trade intent for authorization.

Usage:
    pip install -e ..
    python demo_e2e.py
"""

import asyncio
import hashlib
import os

from irl_sdk import IRLClient, AuthorizeRequest, TradeAction, OrderType

IRL_URL = os.getenv("IRL_URL", "https://irl.macropulse.live")
MTA_URL = os.getenv("MTA_URL")  # only for IRL servers with a regime operator
API_TOKEN = os.getenv("IRL_API_TOKEN", "demo-readonly-1a1bb53fb4bcb5f1ca2c2f48808a35ba")

# Stable demo agent — must be registered in the IRL Engine MAR.
AGENT_ID = "00000000-0000-4000-a000-000000000001"  # demo-crypto-agent in MAR
MODEL_HASH = "cee60d4e409bd88b5e1998ef6ac078498491616a3a321bc76399b94784c4f283"  # sha256(b"demo-crypto-agent-v1")


async def main() -> None:
    print(f"IRL Engine : {IRL_URL}")
    print(f"MTA        : {MTA_URL or 'none (agent caps only)'}")
    print(f"Agent ID   : {AGENT_ID}")
    print(f"Model hash : {MODEL_HASH[:16]}...")
    print()

    async with IRLClient(IRL_URL, API_TOKEN, MTA_URL) as client:
        req = AuthorizeRequest(
            agent_id=AGENT_ID,
            model_id="demo-algo-v1",
            model_hash_hex=MODEL_HASH,
            action=TradeAction.LONG,
            asset="BTC-USD",
            order_type=OrderType.MARKET,
            venue_id="coinbase",
            quantity=0.01,
            notional=650.0,
            notional_currency="USD",
        )

        print("Fetching heartbeat and submitting authorize request...")
        try:
            result = await client.authorize(req)
            print()
            print("AUTHORIZED" if result.authorized else "HALTED")
            print(f"  trace_id      : {result.trace_id}")
            print(f"  reasoning_hash: {result.reasoning_hash[:24]}...")
            print(f"  shadow_blocked: {result.shadow_blocked}")
        except Exception as exc:
            print(f"ERROR: {exc}")


if __name__ == "__main__":
    asyncio.run(main())
