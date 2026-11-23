from flask import Blueprint, current_app, jsonify, request

from app.services.watchlist_service import (
    WatchlistDuplicateError,
    WatchlistNotFoundError,
    WatchlistValidationError,
)
from app.utils.mongo_utils import serialize

watchlist_bp = Blueprint("watchlist", __name__, url_prefix="/api/watchlist")


def _service():
    return current_app.extensions["watchlist_service"]


@watchlist_bp.get("")
def list_watchlist():
    return jsonify({"watchlist": serialize(_service().list(current_app.config["DEFAULT_USER_ID"]))})


@watchlist_bp.post("")
def add_watchlist():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Request body must be a JSON object."}), 400
    try:
        item = _service().add(current_app.config["DEFAULT_USER_ID"], data.get("stock_symbol"))
        return jsonify(serialize(item)), 201
    except WatchlistDuplicateError as exc:
        return jsonify({"error": str(exc)}), 409
    except WatchlistValidationError as exc:
        return jsonify({"error": str(exc)}), 400


@watchlist_bp.delete("/<item_id>")
def remove_watchlist(item_id):
    try:
        _service().remove(current_app.config["DEFAULT_USER_ID"], item_id)
        return jsonify({"deleted": True, "id": item_id})
    except WatchlistNotFoundError as exc:
        return jsonify({"error": str(exc)}), 404
