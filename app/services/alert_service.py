"""Alert rules + evaluation. Business-logic layer for Module 4 (event-driven price alerts)."""
import logging
import math
import re

from app.events.events import PriceFallsBelowThresholdEvent, StockPriceIncreasedEvent
from app.utils.mongo_utils import utcnow

logger = logging.getLogger(__name__)

CONDITIONS = ("ABOVE", "BELOW")
SYMBOL_RE = re.compile(r"^[A-Z0-9.\-^=]{1,15}$")


class AlertValidationError(ValueError):
    pass


class AlertNotFoundError(LookupError):
    pass


def _validate_symbol(value):
    symbol = str(value or "").strip().upper()
    if not SYMBOL_RE.match(symbol):
        raise AlertValidationError("Enter a valid stock symbol, for example AAPL or RELIANCE.NS.")
    return symbol


def _validate_condition(value):
    condition = str(value or "").strip().upper()
    if condition not in CONDITIONS:
        raise AlertValidationError("Condition must be ABOVE or BELOW.")
    return condition


def _validate_price(value):
    if isinstance(value, bool):
        raise AlertValidationError("Target price must be a number greater than zero.")
    try:
        price = float(value)
    except (TypeError, ValueError):
        raise AlertValidationError("Target price must be a number greater than zero.") from None
    if not math.isfinite(price) or price <= 0:
        raise AlertValidationError("Target price must be a number greater than zero.")
    return round(price, 4)


class AlertService:
    def __init__(self, alert_repo, notification_service, dispatcher, user_id="local-user",
                 symbol_validator=None):
        self.alerts = alert_repo
        self.notifications = notification_service
        self.dispatcher = dispatcher
        self.user_id = user_id
        self.symbol_validator = symbol_validator  # optional callable(symbol) -> bool

    # ---- CRUD -------------------------------------------------------------
    def create_alert(self, symbol, condition, target_price):
        symbol = _validate_symbol(symbol)
        condition = _validate_condition(condition)
        target = _validate_price(target_price)
        if self.symbol_validator and not self.symbol_validator(symbol):
            raise AlertValidationError(f"{symbol} is not a known stock symbol.")
        return self.alerts.create(self.user_id, symbol, condition, target)

    def list_alerts(self, symbol=None, status=None):
        flag = {"active": False, "triggered": True}.get((status or "").lower())
        return self.alerts.list(self.user_id, symbol.upper() if symbol else None, flag)

    def update_alert(self, alert_id, condition=None, target_price=None):
        """Editing the condition/target re-arms the alert."""
        if self.alerts.get(alert_id) is None:
            raise AlertNotFoundError("Alert not found.")
        fields = {"is_triggered": False, "triggered_at": None}
        if condition is not None:
            fields["condition"] = _validate_condition(condition)
        if target_price is not None:
            fields["target_price"] = _validate_price(target_price)
        if len(fields) == 2:
            raise AlertValidationError("Provide a new condition or target price.")
        return self.alerts.update(alert_id, fields)

    def reset_alert(self, alert_id):
        if not self.alerts.reset(alert_id):
            raise AlertNotFoundError("Alert not found.")
        return self.alerts.get(alert_id)

    def delete_alert(self, alert_id):
        if not self.alerts.delete(alert_id):
            raise AlertNotFoundError("Alert not found.")

    # ---- Evaluation (called after every fresh price) ------------------------
    @staticmethod
    def _is_hit(alert, price):
        if alert["condition"] == "ABOVE":
            return price >= alert["target_price"]
        return price <= alert["target_price"]

    def evaluate(self, symbol, current_price, previous_price=None, source=None, occurred_at=None):
        """Check all untriggered alerts for `symbol`; return the notifications created."""
        try:
            price = float(current_price)
        except (TypeError, ValueError):
            return []
        if not math.isfinite(price) or price <= 0:
            logger.warning("Ignoring invalid price %r for %s", current_price, symbol)
            return []
        symbol = str(symbol).strip().upper()
        when = occurred_at or utcnow()
        created = []
        for alert in self.alerts.find_active_for_symbol(self.user_id, symbol):
            if not self._is_hit(alert, price):
                continue
            if not self.alerts.claim_trigger(alert["_id"], when):
                continue  # another refresh already triggered it: no duplicate
            event = self._build_event(alert, price, previous_price, source, when)
            try:
                created.extend(self.dispatcher.publish(event, strict=True))
            except Exception:  # noqa: BLE001
                logger.exception("Notification failed for alert %s; re-arming it", alert["_id"])
                self.alerts.release_trigger(alert["_id"])
        return [n for n in created if n]

    @staticmethod
    def _build_event(alert, price, previous, source, when):
        common = dict(stock_symbol=alert["stock_symbol"], current_price=price,
                      previous_price=previous, occurred_at=when, source=source,
                      alert_id=str(alert["_id"]), user_id=alert["user_id"])
        if alert["condition"] == "ABOVE":
            return StockPriceIncreasedEvent(target_price=alert["target_price"], **common)
        return PriceFallsBelowThresholdEvent(threshold_price=alert["target_price"], **common)
