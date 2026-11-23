"""Single entry point that wires Member 2's code into the Flask app.

Member 1's create_app() must (1) put the pymongo Database in app.extensions["mongo_db"], then
(2) call init_alerts_and_ui(app). Member 1's refresh flow then calls notify_price_update(...).
"""
import logging

from flask import current_app

from app.events.event_dispatcher import EventDispatcher
from app.events.events import PriceFallsBelowThresholdEvent, StockPriceIncreasedEvent
from app.repositories.alert_repository import AlertRepository
from app.repositories.notification_repository import NotificationRepository
from app.routes.alert_routes import alerts_bp, register_error_handlers
from app.routes.frontend_routes import frontend_bp
from app.routes.notification_routes import notifications_bp
from app.services.alert_service import AlertService
from app.services.notification_service import NotificationService
from app.utils.mongo_utils import serialize

logger = logging.getLogger(__name__)


def init_alerts_and_ui(app, db=None, symbol_validator=None):
    db = db if db is not None else app.extensions["mongo_db"]
    app.extensions["mongo_db"] = db
    user_id = app.config.get("DEFAULT_USER_ID", "local-user")

    def currency_lookup(symbol):
        doc = db["stocks"].find_one({"symbol": symbol}, {"currency": 1})
        return (doc or {}).get("currency")

    dispatcher = EventDispatcher()
    notification_service = NotificationService(
        NotificationRepository(db), currency_lookup, app.config.get("DEFAULT_CURRENCY", "INR"))
    dispatcher.subscribe(StockPriceIncreasedEvent, notification_service.handle_event)
    dispatcher.subscribe(PriceFallsBelowThresholdEvent, notification_service.handle_event)
    alert_service = AlertService(AlertRepository(db), notification_service, dispatcher,
                                 user_id=user_id, symbol_validator=symbol_validator)

    app.extensions["event_dispatcher"] = dispatcher
    app.extensions["notification_service"] = notification_service
    app.extensions["alert_service"] = alert_service

    register_error_handlers(app)
    for bp in (alerts_bp, notifications_bp, frontend_bp):
        app.register_blueprint(bp)
    return app


def notify_price_update(symbol, price, previous_price=None, source=None, occurred_at=None):
    """Hook for StockService.refresh_price(): evaluate alerts after a fresh price was saved.

    Returns a JSON-safe list of the notifications created. Never raises, so a problem in the
    alert engine can never break a price refresh.
    """
    service = current_app.extensions.get("alert_service")
    if service is None:
        return []
    try:
        return serialize(service.evaluate(symbol, price, previous_price, source, occurred_at))
    except Exception:  # noqa: BLE001
        logger.exception("Alert evaluation failed for %s", symbol)
        return []
