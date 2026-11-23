# Integration contract: what Member 1 must do

Member 2 delivers the alerts, events, notifications, UI, Docker, Jenkins and Kubernetes. The two halves meet in
**three places**: app startup, the price-refresh hook, and the JSON API shapes the UI reads.
`dev/mock_server.py` is a working reference implementation of everything below. Run it with
`python -m dev.mock_server` and compare against it.

## 1. Files to merge (no overwrite)

| Path | Note |
|---|---|
| `app/integration.py` | Member 2. Single entry point (`init_alerts_and_ui`, `notify_price_update`). |
| `app/events/`, `app/services/alert_service.py`, `notification_service.py` | Member 2. |
| `app/repositories/alert_repository.py`, `notification_repository.py` | **Member 2 owns these two.** Do not write your own `price_alerts` / `notifications` repositories. |
| `app/routes/alert_routes.py`, `notification_routes.py`, `frontend_routes.py` | Member 2. Do not add `/api/alerts*`, `/api/notifications*` or a `/` route. |
| `app/utils/mongo_utils.py` | Member 2. Reuse `utcnow`, `to_object_id`, `serialize` if helpful. |
| `frontend/` | Member 2 (served by `frontend_routes.py`). |
| `requirements.txt`, `.env.example`, `.gitignore`, `.flake8`, `pytest.ini` | **Merge by hand**: union of both members' lines. |
| `app/__init__.py` | **Yours.** Not included in this package. Empty `__init__.py` files in subpackages are identical, so git merges them cleanly. |

## 2. Change 1: app startup (`app/__init__.py`)

```python
def create_app():
    app = Flask(__name__)
    app.config["DEFAULT_USER_ID"] = os.getenv("DEFAULT_USER_ID", "local-user")
    app.config["DEFAULT_CURRENCY"] = os.getenv("DEFAULT_CURRENCY", "INR")

    db = MongoClient(os.environ["MONGODB_URI"]).get_default_database()   # or your own connection module
    app.extensions["mongo_db"] = db            # REQUIRED key name: a pymongo Database

    # ... create your repositories/services, register YOUR blueprints ...

    from app.integration import init_alerts_and_ui
    init_alerts_and_ui(app)                    # call LAST. Registers alerts, notifications, UI, /health, /ready
    return app
```

* `create_app()` must exist in `app/__init__.py` because the Dockerfile runs `gunicorn "app:create_app()"`.
* Optional: validate alert symbols against your provider with
  `init_alerts_and_ui(app, symbol_validator=lambda s: stock_service.symbol_exists(s))`.

## 3. Change 2: price-refresh hook (`StockService.refresh_price` or the refresh route)

```python
from app.integration import notify_price_update

# AFTER the new price snapshot has been saved and the stock document updated:
triggered = notify_price_update(
    symbol,                 # "AAPL"
    price,                  # float, latest price
    previous_price,         # float or None (the price before this refresh)
    source,                 # "Alpha Vantage" / "Mock provider"
    fetched_at,             # datetime (UTC) of the quote
)
response["triggered_alerts"] = triggered   # list, may be empty
```

Rules:
1. Call it **only when you obtained a fresh price from the provider**. Do **not** call it when serving a cached
   snapshot because Alpha Vantage failed or rate-limited.
2. It is safe to call inside a request: it never raises and returns `[]` if anything goes wrong.
3. It needs a Flask app context (a normal request already has one).
4. Do not evaluate alerts anywhere else (no second implementation).

## 4. Change 3: demo price override (needed for the viva demo)

The demo needs prices of 1650 and then 2005, which real market data will not give you on demand.
Support an optional body on the refresh endpoint, enabled only when your `MockStockDataProvider` is active
(or `ENABLE_PRICE_OVERRIDE=true`):

```
POST /api/stocks/AAPL/refresh      {"price": 2005}
```
It must flow through the **same** save-snapshot, then `notify_price_update` path as a real price. State in the viva
that overridden prices are simulated.

## 5. MongoDB data requirements

* `stocks` documents must have **`symbol`** (upper-case) and **`currency`** (`"INR"`, `"USD"`, ...). The notification text
  uses them (`$200.00` vs `₹1,650.00`). Missing currency falls back to `DEFAULT_CURRENCY`.
* Collections Member 2 creates and owns: `price_alerts`, `notifications` (indexes are created automatically).
* Every document uses `user_id = "local-user"` (value of `DEFAULT_USER_ID`).
* Store timestamps as UTC `datetime` objects.

## 6. API contract the UI relies on

* JSON everywhere. Timestamps are ISO-8601 UTC strings ending in `Z`. ObjectIds are returned as strings.
* Errors: HTTP 400 (validation), 404 (not found), 409 (duplicate), 502/503 (provider unavailable) with body
  `{"error": "plain-language message"}`. The UI shows this text verbatim, so write it for end users.
* The UI does **not** call `/api/dashboard`; it builds the dashboard from the endpoints below. You may still
  implement `/api/dashboard` as the plan requires (shape is yours).

| Endpoint | Request | Success response |
|---|---|---|
| `GET /api/stocks?q=AAPL` | `q` required | `200 {"results":[{"symbol","name","exchange","currency"}]}` (empty list if none, `400` if `q` blank) |
| `GET /api/stocks/<symbol>` | | `200` **stock object** (below); `404` unknown symbol |
| `POST /api/stocks/<symbol>/refresh` | optional `{"price": n}` (section 4) | `200` stock object **plus** `"triggered_alerts": [...]`. If provider is down but a cached price exists: still `200`, with `"cached": true` and `"warning": "message"`. No cache: `503`. |
| `GET /api/watchlist` | | `200 {"watchlist":[{"_id","stock_symbol","added_at", ...stock fields}]}` (include `name, exchange, currency, last_price, previous_close, price_timestamp, data_source` when known) |
| `POST /api/watchlist` | `{"stock_symbol":"AAPL"}` | `201` the item; `400` invalid symbol; `409` duplicate |
| `DELETE /api/watchlist/<_id>` | | `200 {"deleted": true}`; `404` |
| `GET /api/portfolio` | | `200` portfolio object (below) |
| `POST /api/portfolio/buy` | `{"stock_symbol","quantity":int,"price":number}` | `201` the transaction |
| `POST /api/portfolio/sell` | same | `201` the transaction; `400` if quantity exceeds holding |
| `GET /api/transactions` | | `200 {"transactions":[...]}` newest first |

**Stock object**
```json
{"symbol":"AAPL","name":"Apple Inc.","exchange":"NASDAQ","currency":"USD",
 "last_price":185.5,"previous_close":184.2,"price_timestamp":"2026-11-17T18:30:00Z",
 "data_source":"Alpha Vantage","cached":false}
```
**Portfolio object**
```json
{"holdings":[{"stock_symbol":"AAPL","quantity":15,"total_cost_basis":23000.0,"average_purchase_price":1533.33,
  "current_price":1650.0,"current_value":24750.0,"unrealized_profit_loss":1750.0,"realized_profit_loss":0.0,
  "currency":"INR","price_timestamp":"...Z","data_source":"Alpha Vantage"}],
 "summary":{"total_invested":23000.0,"current_value":24750.0,"unrealized_profit_loss":1750.0,
  "realized_profit_loss":0.0,"return_percentage":7.61}}
```
Only holdings with quantity > 0 appear in `holdings`; `realized_profit_loss` in `summary` must still include fully sold positions.
**Transaction object:** `{"_id","stock_symbol","transaction_type":"BUY"|"SELL","quantity","price","total_amount","timestamp"}`.

### Endpoints Member 2 provides (you only consume `triggered_alerts`)
`GET/POST /api/alerts`, `PUT/DELETE /api/alerts/<id>`, `POST /api/alerts/<id>/reset`, `GET /api/notifications[?unread=true]`,
`POST /api/notifications/<id>/read`, `POST /api/notifications/read-all`, `GET /` (UI), `GET /health`, `GET /ready`.

## 7. Environment variables (names are fixed, used by Docker, Compose, Jenkins and K8s)

`ALPHA_VANTAGE_API_KEY`, `MONGODB_URI` (must include the db name, e.g. `mongodb://mongo:27017/equitrack`),
`FLASK_ENV`, `DEFAULT_USER_ID`, `DEFAULT_CURRENCY`. Read the key from the environment only.

## 8. Tests and CI expectations

* Tests must pass **without network or a running MongoDB** (use `mongomock` and `MockStockDataProvider`). Jenkins runs
  `flake8 app tests dev` and `pytest tests/` and fails the build otherwise.
* Keep your test filenames distinct (`test_stocks.py`, `test_portfolio.py`); mine are `test_alerts.py`,
  `test_events_and_notifications.py`, `test_ui_and_integration.py`, and `tests/conftest.py` (merge fixtures if you also have one).
* `tests/test_ui_and_integration.py::test_full_demo_scenario` encodes the final demo flow against the mock backend. Once your
  real backend is in, copy it as an end-to-end test against your `create_app()` with `MockStockDataProvider` (TC-19/TC-20).

## 9. Cross-review (evidence for marks)

Member 1 reviews Member 2's PRs for: alert evaluation and duplicate prevention (`AlertRepository.claim_trigger`),
the refresh hook, and the Dockerfile. Member 2 reviews: provider fallback chain, portfolio calculations, API key handling.

## 10. Integration checklist (run together after merge)

1. `docker compose up --build`, then open http://localhost:5000
2. Search `AAPL`, open details: price, timestamp and source are visible.
3. Add to watchlist; adding again shows "already on your watchlist".
4. Buy 15 at 1533.33; refresh with `{"price":1650}`; portfolio shows 24,750 / +1,750 / 7.61%.
5. Create alert ABOVE 2000; refresh with `{"price":2005}`; toast + one notification + alert marked Triggered.
6. Refresh again with 2010; no new notification.
7. Sell 5; holdings 10, realized P/L and transaction history update; selling 99 shows an error.
8. `docker compose restart web mongo` (and later `kubectl delete pod`); data is still there (NFR-11).
9. Stop network or use a bad key; the UI shows cached price with a "cached" tag or a clear error (TC-18).
