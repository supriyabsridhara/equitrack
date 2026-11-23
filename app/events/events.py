"""Domain events published by the alert engine (Event-Driven Notification pattern)."""
from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar, Optional


@dataclass(kw_only=True)
class PriceEvent:
    stock_symbol: str
    current_price: float
    previous_price: Optional[float]
    occurred_at: datetime
    source: Optional[str]
    alert_id: str
    user_id: str = "local-user"
    event_type: ClassVar[str] = "PRICE_EVENT"


@dataclass(kw_only=True)
class StockPriceIncreasedEvent(PriceEvent):
    """Price rose to / above the user's ABOVE target."""
    target_price: float
    event_type: ClassVar[str] = "PRICE_INCREASED_ABOVE_TARGET"


@dataclass(kw_only=True)
class PriceFallsBelowThresholdEvent(PriceEvent):
    """Price fell to / below the user's BELOW threshold."""
    threshold_price: float
    event_type: ClassVar[str] = "PRICE_FELL_BELOW_THRESHOLD"
