"""TC-12 .. TC-17: alert creation, validation, event generation, duplicate prevention, re-arming."""
import pytest

from app.events.events import PriceFallsBelowThresholdEvent, StockPriceIncreasedEvent
from app.services.alert_service import AlertNotFoundError, AlertValidationError


def test_tc12_create_valid_alert(client):
    res = client.post("/api/alerts", json={"stock_symbol": "infy", "condition": "above", "target_price": "1650"})
    assert res.status_code == 201
    body = res.get_json()
    assert body["stock_symbol"] == "INFY" and body["condition"] == "ABOVE"
    assert body["target_price"] == 1650.0 and body["status"] == "ACTIVE" and body["is_triggered"] is False
    assert len(client.get("/api/alerts").get_json()["alerts"]) == 1


@pytest.mark.parametrize("payload", [
    {"stock_symbol": "", "condition": "ABOVE", "target_price": 10},
    {"stock_symbol": "AA PL", "condition": "ABOVE", "target_price": 10},
    {"stock_symbol": "AAPL", "condition": "SIDEWAYS", "target_price": 10},
    {"stock_symbol": "AAPL", "condition": "ABOVE", "target_price": 0},
    {"stock_symbol": "AAPL", "condition": "ABOVE", "target_price": -5},
    {"stock_symbol": "AAPL", "condition": "ABOVE", "target_price": "abc"},
    {"stock_symbol": "AAPL", "condition": "ABOVE", "target_price": True},
    {"stock_symbol": "AAPL", "condition": "ABOVE", "target_price": float("inf")},
    {"stock_symbol": "AAPL", "condition": "ABOVE"},
])
def test_tc13_invalid_alert_rejected(client, payload):
    res = client.post("/api/alerts", json=payload)
    assert res.status_code == 400 and res.get_json()["error"]
    assert client.get("/api/alerts").get_json()["alerts"] == []


def test_non_json_body_rejected(client):
    assert client.post("/api/alerts", data="nope").status_code == 400


def test_symbol_validator_is_used(app, db):
    svc = app.extensions["alert_service"]
    svc.symbol_validator = lambda s: s == "AAPL"
    svc.create_alert("AAPL", "ABOVE", 10)
    with pytest.raises(AlertValidationError):
        svc.create_alert("ZZZZ", "ABOVE", 10)


def test_tc14_price_reaches_target_generates_event_and_notification(app, svc):
    seen = []
    app.extensions["event_dispatcher"].subscribe(StockPriceIncreasedEvent, seen.append)
    svc.create_alert("INFY", "ABOVE", 1650)
    created = svc.evaluate("INFY", 1660, previous_price=1620, source="Sample")
    assert len(created) == 1 and len(seen) == 1
    assert seen[0].target_price == 1650 and seen[0].current_price == 1660 and seen[0].source == "Sample"
    assert "reached your target" in created[0]["message"]
    assert svc.list_alerts()[0]["is_triggered"] is True


def test_target_is_inclusive(svc):
    svc.create_alert("INFY", "ABOVE", 1650)
    assert len(svc.evaluate("INFY", 1650)) == 1


def test_tc15_price_falls_below_threshold(app, svc):
    seen = []
    app.extensions["event_dispatcher"].subscribe(PriceFallsBelowThresholdEvent, seen.append)
    svc.create_alert("TCS", "BELOW", 3250)
    created = svc.evaluate("TCS", 3200)
    assert len(created) == 1 and seen[0].threshold_price == 3250
    assert "fell below your threshold" in created[0]["message"]


def test_condition_not_met_creates_nothing(svc):
    svc.create_alert("INFY", "ABOVE", 1650)
    svc.create_alert("INFY", "BELOW", 1500)
    assert svc.evaluate("INFY", 1600) == []
    assert all(not a["is_triggered"] for a in svc.list_alerts())


def test_other_symbols_are_not_evaluated(svc):
    svc.create_alert("INFY", "ABOVE", 100)
    assert svc.evaluate("TCS", 5000) == []


def test_tc16_no_duplicate_notification(client, svc):
    svc.create_alert("INFY", "ABOVE", 1650)
    assert len(svc.evaluate("INFY", 1660)) == 1
    assert svc.evaluate("INFY", 1670) == []
    assert svc.evaluate("INFY", 1700) == []
    assert len(client.get("/api/notifications").get_json()["notifications"]) == 1


def test_claim_is_atomic(app, svc):
    alert = svc.create_alert("INFY", "ABOVE", 1)
    repo = svc.alerts
    from app.utils.mongo_utils import utcnow
    assert repo.claim_trigger(alert["_id"], utcnow()) is True
    assert repo.claim_trigger(alert["_id"], utcnow()) is False


def test_tc17_reset_rearms_alert(client, svc):
    alert = client.post("/api/alerts", json={"stock_symbol": "INFY", "condition": "ABOVE", "target_price": 1650}).get_json()
    svc.evaluate("INFY", 1660)
    assert client.get("/api/alerts?status=triggered").get_json()["alerts"][0]["status"] == "TRIGGERED"
    assert client.post(f"/api/alerts/{alert['id']}/reset").get_json()["is_triggered"] is False
    assert len(svc.evaluate("INFY", 1661)) == 1
    assert len(client.get("/api/notifications").get_json()["notifications"]) == 2


def test_editing_alert_rearms_it(client, svc):
    alert = client.post("/api/alerts", json={"stock_symbol": "INFY", "condition": "ABOVE", "target_price": 1650}).get_json()
    svc.evaluate("INFY", 1660)
    res = client.put(f"/api/alerts/{alert['id']}", json={"target_price": 1700})
    assert res.status_code == 200 and res.get_json()["is_triggered"] is False
    assert res.get_json()["target_price"] == 1700
    assert svc.evaluate("INFY", 1665) == []
    assert len(svc.evaluate("INFY", 1705)) == 1


def test_edit_requires_a_change_and_valid_values(client):
    alert = client.post("/api/alerts", json={"stock_symbol": "INFY", "condition": "ABOVE", "target_price": 1650}).get_json()
    assert client.put(f"/api/alerts/{alert['id']}", json={}).status_code == 400
    assert client.put(f"/api/alerts/{alert['id']}", json={"target_price": -1}).status_code == 400


def test_delete_and_not_found(client):
    alert = client.post("/api/alerts", json={"stock_symbol": "INFY", "condition": "ABOVE", "target_price": 1650}).get_json()
    assert client.delete(f"/api/alerts/{alert['id']}").status_code == 200
    assert client.delete(f"/api/alerts/{alert['id']}").status_code == 404
    assert client.post("/api/alerts/not-an-id/reset").status_code == 404
    assert client.put("/api/alerts/not-an-id", json={"target_price": 5}).status_code == 404


@pytest.mark.parametrize("bad", [None, 0, -10, "x", float("nan")])
def test_invalid_prices_are_ignored(svc, bad):
    svc.create_alert("INFY", "BELOW", 1500)
    assert svc.evaluate("INFY", bad) == []
    assert svc.list_alerts()[0]["is_triggered"] is False


def test_failed_notification_rearms_alert(app, svc):
    svc.create_alert("INFY", "ABOVE", 1650)
    notifier = app.extensions["notification_service"]
    original = notifier.repo.create
    notifier.repo.create = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("db down"))
    assert svc.evaluate("INFY", 1700) == []
    assert svc.list_alerts()[0]["is_triggered"] is False  # can fire on the next refresh
    notifier.repo.create = original
    assert len(svc.evaluate("INFY", 1700)) == 1


def test_multiple_alerts_same_symbol(svc):
    svc.create_alert("INFY", "ABOVE", 1600)
    svc.create_alert("INFY", "ABOVE", 1650)
    svc.create_alert("INFY", "ABOVE", 1800)
    assert len(svc.evaluate("INFY", 1660)) == 2


def test_not_found_error_type(svc):
    with pytest.raises(AlertNotFoundError):
        svc.delete_alert("507f1f77bcf86cd799439011")
