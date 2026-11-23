from datetime import datetime, timezone

from app.events.event_dispatcher import EventDispatcher
from app.events.events import PriceEvent, StockPriceIncreasedEvent


def _event():
    return StockPriceIncreasedEvent(stock_symbol="INFY", current_price=1660, previous_price=1620,
                                    occurred_at=datetime.now(timezone.utc), source="t", alert_id="a1",
                                    target_price=1650)


def test_dispatcher_calls_subscribers_and_returns_results():
    d, calls = EventDispatcher(), []
    d.subscribe(StockPriceIncreasedEvent, lambda e: calls.append(e) or "ok")
    assert d.publish(_event()) == ["ok"] and len(calls) == 1


def test_dispatcher_base_class_subscription_and_unsubscribe():
    d, calls = EventDispatcher(), []
    handler = calls.append
    d.subscribe(PriceEvent, handler)
    d.publish(_event())
    d.unsubscribe(PriceEvent, handler)
    d.publish(_event())
    assert len(calls) == 1


def test_dispatcher_isolates_failing_handler():
    d, calls = EventDispatcher(), []
    d.subscribe(StockPriceIncreasedEvent, lambda e: 1 / 0)
    d.subscribe(StockPriceIncreasedEvent, lambda e: calls.append(e))
    d.publish(_event())
    assert len(calls) == 1


def test_dispatcher_strict_reraises():
    d = EventDispatcher()
    d.subscribe(StockPriceIncreasedEvent, lambda e: 1 / 0)
    try:
        d.publish(_event(), strict=True)
        assert False, "expected ZeroDivisionError"
    except ZeroDivisionError:
        pass


def test_duplicate_subscription_ignored():
    d, calls = EventDispatcher(), []
    d.subscribe(StockPriceIncreasedEvent, calls.append)
    d.subscribe(StockPriceIncreasedEvent, calls.append)
    d.publish(_event())
    assert len(calls) == 1


def test_notification_read_flow(client, svc):
    svc.create_alert("INFY", "ABOVE", 1)
    svc.create_alert("TCS", "BELOW", 9999)
    svc.evaluate("INFY", 5)
    svc.evaluate("TCS", 5)
    body = client.get("/api/notifications").get_json()
    assert body["unread_count"] == 2 and len(body["notifications"]) == 2
    first = body["notifications"][0]
    assert client.post(f"/api/notifications/{first['id']}/read").status_code == 200
    assert client.get("/api/notifications?unread=true").get_json()["unread_count"] == 1
    assert client.post("/api/notifications/read-all").get_json()["updated"] == 1
    assert client.get("/api/notifications?unread=true").get_json()["notifications"] == []
    assert client.post("/api/notifications/bad-id/read").status_code == 404


def test_message_uses_stock_currency(app, db, svc):
    db.stocks.insert_one({"symbol": "AAPL", "currency": "USD"})
    svc.create_alert("AAPL", "ABOVE", 200)
    msg = svc.evaluate("AAPL", 205.5)[0]["message"]
    assert "$200.00" in msg and "$205.50" in msg


def test_message_defaults_to_rupees(svc):
    svc.create_alert("INFY", "ABOVE", 1650)
    assert "₹1,650.00" in svc.evaluate("INFY", 1660)[0]["message"]
