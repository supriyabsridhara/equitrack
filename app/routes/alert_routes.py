"""REST endpoints for price alerts."""
from flask import Blueprint, current_app, jsonify, request

from app.services.alert_service import AlertNotFoundError, AlertValidationError
from app.utils.mongo_utils import serialize

alerts_bp = Blueprint("alerts", __name__, url_prefix="/api/alerts")


def _svc():
    return current_app.extensions["alert_service"]


def _body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise AlertValidationError("Request body must be a JSON object.")
    return data


def _view(alert):
    out = serialize(alert)
    out["status"] = "TRIGGERED" if alert.get("is_triggered") else "ACTIVE"
    return out


@alerts_bp.get("")
def list_alerts():
    alerts = _svc().list_alerts(request.args.get("symbol"), request.args.get("status"))
    return jsonify({"alerts": [_view(a) for a in alerts]})


@alerts_bp.post("")
def create_alert():
    data = _body()
    alert = _svc().create_alert(data.get("stock_symbol"), data.get("condition"), data.get("target_price"))
    return jsonify(_view(alert)), 201


@alerts_bp.put("/<alert_id>")
def update_alert(alert_id):
    data = _body()
    alert = _svc().update_alert(alert_id, data.get("condition"), data.get("target_price"))
    return jsonify(_view(alert))


@alerts_bp.post("/<alert_id>/reset")
def reset_alert(alert_id):
    return jsonify(_view(_svc().reset_alert(alert_id)))


@alerts_bp.delete("/<alert_id>")
def delete_alert(alert_id):
    _svc().delete_alert(alert_id)
    return jsonify({"deleted": True, "id": alert_id})


def register_error_handlers(app):
    @app.errorhandler(AlertValidationError)
    def _bad_request(err):
        return jsonify({"error": str(err)}), 400

    @app.errorhandler(AlertNotFoundError)
    def _not_found(err):
        return jsonify({"error": str(err)}), 404
