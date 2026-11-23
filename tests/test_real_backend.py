import mongomock
import pytest

from app import create_app
from app.providers.mock_stock_data_provider import MockStockDataProvider


@pytest.fixture
def real_app():
    db = mongomock.MongoClient()["equitrack_real_test"]
    app = create_app(
        {
            "TESTING": True,
            "ENABLE_PRICE_OVERRIDE": True,
            "STOCK_DATA_PROVIDER": "mock",
            "DEFAULT_USER_ID": "test-user",
        },
        db=db,
        provider=MockStockDataProvider(),
    )
    return app


@pytest.fixture
def real_client(real_app):
    return real_app.test_client()


def test_stock_search_details_and_refresh(real_app, real_client):
    results = real_client.get("/api/stocks?q=apple")
    assert results.status_code == 200
    assert results.get_json()["results"][0]["symbol"] == "AAPL"

    details = real_client.get("/api/stocks/AAPL")
    assert details.status_code == 200
    assert details.get_json()["name"] == "Apple Inc."

    refreshed = real_client.post(
        "/api/stocks/AAPL/refresh",
        json={"price": 1650},
    )
    assert refreshed.status_code == 200
    assert refreshed.get_json()["last_price"] == 1650
    assert refreshed.get_json()["triggered_alerts"] == []


def test_watchlist_duplicate_is_database_enforced(real_client):
    first = real_client.post("/api/watchlist", json={"stock_symbol": "AAPL"})
    duplicate = real_client.post("/api/watchlist", json={"stock_symbol": "AAPL"})
    assert first.status_code == 201
    assert duplicate.status_code == 409
    assert len(real_client.get("/api/watchlist").get_json()["watchlist"]) == 1


def test_weighted_average_buy_sell_and_transaction_history(real_client):
    assert real_client.post(
        "/api/portfolio/buy",
        json={"stock_symbol": "AAPL", "quantity": 15, "price": 1533.33},
    ).status_code == 201

    refreshed = real_client.post(
        "/api/stocks/AAPL/refresh",
        json={"price": 1650},
    )
    assert refreshed.status_code == 200

    portfolio = real_client.get("/api/portfolio").get_json()
    assert portfolio["summary"]["current_value"] == 24750
    assert portfolio["summary"]["unrealized_profit_loss"] == 1750.05
    assert portfolio["summary"]["return_percentage"] == 7.61
    assert portfolio["holdings"][0]["average_purchase_price"] == 1533.33

    sold = real_client.post(
        "/api/portfolio/sell",
        json={"stock_symbol": "AAPL", "quantity": 5, "price": 2010},
    )
    assert sold.status_code == 201

    too_many = real_client.post(
        "/api/portfolio/sell",
        json={"stock_symbol": "AAPL", "quantity": 99, "price": 2010},
    )
    assert too_many.status_code == 400

    portfolio = real_client.get("/api/portfolio").get_json()
    holding = portfolio["holdings"][0]
    assert holding["quantity"] == 10
    assert holding["realized_profit_loss"] > 0

    transactions = real_client.get("/api/transactions").get_json()["transactions"]
    assert len(transactions) == 2
    assert transactions[0]["transaction_type"] == "SELL"


def test_real_backend_alert_triggers_once(real_client):
    created = real_client.post(
        "/api/alerts",
        json={"stock_symbol": "AAPL", "condition": "ABOVE", "target_price": 2000},
    )
    assert created.status_code == 201

    hit = real_client.post(
        "/api/stocks/AAPL/refresh",
        json={"price": 2005},
    ).get_json()
    again = real_client.post(
        "/api/stocks/AAPL/refresh",
        json={"price": 2010},
    ).get_json()

    assert len(hit["triggered_alerts"]) == 1
    assert again["triggered_alerts"] == []
    assert len(real_client.get("/api/notifications").get_json()["notifications"]) == 1
