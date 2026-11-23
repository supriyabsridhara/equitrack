"""End-to-end demo flow against the mock backend + serving of the UI and probes."""


def test_ui_and_probes_are_served(mock_client):
    page = mock_client.get("/")
    assert page.status_code == 200 and b"EquiTrack" in page.data
    assert mock_client.get("/assets/js/app.js").status_code == 200
    assert mock_client.get("/assets/css/app.css").status_code == 200
    assert mock_client.get("/health").get_json()["status"] == "ok"
    assert mock_client.get("/ready").status_code == 200


def test_tc20_refresh_response_carries_source_and_timestamp(mock_client):
    data = mock_client.post("/api/stocks/AAPL/refresh", json={"price": 190}).get_json()
    assert data["data_source"] and data["price_timestamp"] and data["last_price"] == 190


def test_full_demo_scenario(mock_client):
    c = mock_client
    assert c.post("/api/watchlist", json={"stock_symbol": "AAPL"}).status_code == 201
    assert c.post("/api/watchlist", json={"stock_symbol": "AAPL"}).status_code == 409
    assert c.post("/api/portfolio/buy", json={"stock_symbol": "AAPL", "quantity": 15, "price": 1533.33}).status_code == 201
    c.post("/api/stocks/AAPL/refresh", json={"price": 1650})
    summary = c.get("/api/portfolio").get_json()["summary"]
    assert summary["current_value"] == 24750 and summary["return_percentage"] == 7.61
    c.post("/api/alerts", json={"stock_symbol": "AAPL", "condition": "ABOVE", "target_price": 2000})

    hit = c.post("/api/stocks/AAPL/refresh", json={"price": 2005}).get_json()
    assert len(hit["triggered_alerts"]) == 1
    again = c.post("/api/stocks/AAPL/refresh", json={"price": 2010}).get_json()
    assert again["triggered_alerts"] == []
    assert len(c.get("/api/notifications").get_json()["notifications"]) == 1

    assert c.post("/api/portfolio/sell", json={"stock_symbol": "AAPL", "quantity": 5, "price": 2010}).status_code == 201
    assert c.post("/api/portfolio/sell", json={"stock_symbol": "AAPL", "quantity": 99, "price": 2010}).status_code == 400
    holding = c.get("/api/portfolio").get_json()["holdings"][0]
    assert holding["quantity"] == 10 and holding["realized_profit_loss"] > 0
    assert len(c.get("/api/transactions").get_json()["transactions"]) == 2
