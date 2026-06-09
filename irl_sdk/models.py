"""Data models matching the IRL Engine wire format."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class TradeAction(str, Enum):
    LONG = "Long"
    SHORT = "Short"
    NEUTRAL = "Neutral"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"
    TWAP = "TWAP"
    VWAP = "VWAP"
    IOC = "IOC"
    FOK = "FOK"
    POST_ONLY = "POST_ONLY"
    PEGGED = "PEGGED"
    TRAILING_STOP = "TRAILING_STOP"
    ICEBERG = "ICEBERG"


@dataclass
class AuthorizeRequest:
    # Agent identity
    agent_id: str                    # UUID string — must be registered in the MAR
    model_id: str                    # Human-readable model identifier
    model_hash_hex: str              # SHA-256 of the agent's model weights (hex)
    prompt_version: str = "v1"
    feature_schema_id: str = "default"
    hyperparameter_checksum: str = "0" * 64

    # Trade intent
    action: TradeAction = TradeAction.NEUTRAL
    asset: str = ""
    order_type: OrderType = OrderType.MARKET
    venue_id: str = ""
    quantity: float = 0.0
    notional: float = 0.0
    notional_currency: str = "USD"
    multiplier: float = 1.0
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    client_order_id: Optional[str] = None
    reduce_only: bool = False

    # Temporal context
    agent_valid_time: int = 0        # Unix ms of the agent's decision time

    # Multi-agent linking — set when this decision was triggered by another agent's trace
    parent_trace_id: Optional[str] = None

    # Filled automatically by IRLClient.authorize()
    heartbeat: Optional[dict] = None
    regulatory: Optional[dict] = None


@dataclass
class AuthorizeResult:
    trace_id: str
    reasoning_hash: str
    authorized: bool
    shadow_blocked: bool


@dataclass
class BindExecutionRequest:
    trace_id: str
    exchange_tx_id: str
    execution_status: str            # "Filled" | "PartialFill" | "Rejected" | "Expired"
    asset: str
    executed_quantity: float
    execution_price: float


@dataclass
class BindExecutionResult:
    final_proof: str
    status: str
