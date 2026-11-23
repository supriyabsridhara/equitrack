from flask import Blueprint, current_app, jsonify, request

from app.integration import notify_price_update
from app.providers.alpha_vantage_provider import StockDataError
from app.services.stock_service import (
    StockNotFoundError,
    StockValidationError,
)
from app.utils.mongo_utils import serialize

stock_bp = Blueprint("stocks", __name__, url_prefix="/api/stocks")


def _service():
    return current_app.extensions["stock_service"]


@stock_bp.get("")
def search_stocks():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"error": "Enter a ticker symbol to search."}), 400
    try:
        results = _service().search(q)
        return jsonify({"results": serialize(results)})
    except StockValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    except StockDataError as exc:
        return jsonify({"error": str(exc)}), 503


@stock_bp.get("/<symbol>")
def stock_details(symbol):
    try:
        details = _service().get_details(symbol)
        return jsonify(serialize(details))
    except StockNotFoundError as exc:
        return jsonify({"error": str(exc)}), 404
    except StockValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    except StockDataError as exc:
        cached = _service().cached_stock(symbol)
        if cached:
            cached["warning"] = "The live provider is unavailable. Showing the most recent saved price."
            return jsonify(serialize(cached))
        return jsonify({"error": str(exc)}), 503


@stock_bp.post("/<symbol>/refresh")
def refresh_stock(symbol):
    service = _service()
    forced = None
    body = request.get_json(silent=True)
    if isinstance(body, dict) and "price" in body:
        forced = body["price"]
        if not current_app.config.get("ENABLE_PRICE_OVERRIDE", False):
            override_provider = current_app.config.get("STOCK_DATA_PROVIDER")
            if override_provider not in {"mock", "mock_stock"}:
                return jsonify({"error": "Price overrides are disabled. Use a live stock refresh."}), 400
    try:
        details = service.refresh_price(symbol, forced)
    except StockValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    except StockNotFoundError as exc:
        return jsonify({"error": str(exc)}), 404
    except StockDataError as exc:
        cached = service.cached_stock(symbol)
        if cached:
            cached["cached"] = True
            cached["warning"] = "The live provider is unavailable. Showing the most recent saved price."
            return jsonify(serialize(cached)), 200
        return jsonify({"error": str(exc)}), 503
    except Exception as exc:
        if isinstance(exc, LookupError):
            return jsonify({"error": str(exc)}), 404
        return jsonify({"error": "Unable to refresh the stock price. Please try again."}), 502

    previous = details["previous_close"]
    triggered = notify_price_update(
        details["symbol"],
        details["last_price"],
        previous,
        details["data_source"],
        details["price_timestamp"],
    )
    details["triggered_alerts"] = triggered
    return jsonify(serialize(details))
