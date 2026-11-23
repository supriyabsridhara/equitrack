from flask import Blueprint, current_app, jsonify, request

from app.services.portfolio_service import PortfolioValidationError
from app.utils.mongo_utils import serialize

portfolio_bp = Blueprint("portfolio", __name__)


def _service():
    return current_app.extensions["portfolio_service"]


def _body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise PortfolioValidationError("Request body must be a JSON object.")
    return data


@portfolio_bp.get("/api/portfolio")
def portfolio_summary():
    return jsonify(serialize(_service().summary()))


@portfolio_bp.post("/api/portfolio/buy")
def buy_shares():
    try:
        data = _body()
        transaction = _service().buy(
            data.get("stock_symbol"),
            data.get("quantity"),
            data.get("price"),
        )
        return jsonify(serialize(transaction)), 201
    except PortfolioValidationError as exc:
        return jsonify({"error": str(exc)}), 400


@portfolio_bp.post("/api/portfolio/sell")
def sell_shares():
    try:
        data = _body()
        transaction = _service().sell(
            data.get("stock_symbol"),
            data.get("quantity"),
            data.get("price"),
        )
        return jsonify(serialize(transaction)), 201
    except PortfolioValidationError as exc:
        return jsonify({"error": str(exc)}), 400


@portfolio_bp.get("/api/transactions")
def list_transactions():
    transactions = _service().transaction_repo.list(
        current_app.config["DEFAULT_USER_ID"]
    )
    return jsonify({"transactions": serialize(transactions)})


@portfolio_bp.get("/api/dashboard")
def dashboard():
    portfolio = _service().summary()
    watchlist = current_app.extensions["watchlist_service"].list(
        current_app.config["DEFAULT_USER_ID"]
    )
    alerts = current_app.extensions["alert_service"].list_alerts()
    notifications = current_app.extensions["notification_service"].list(
        current_app.config["DEFAULT_USER_ID"]
    )
    return jsonify(serialize({
        "portfolio": portfolio,
        "watchlist": watchlist,
        "alerts": alerts,
        "notifications": notifications,
    }))
