"""REST endpoints for notifications."""
from flask import Blueprint, current_app, jsonify, request

from app.services.alert_service import AlertNotFoundError
from app.utils.mongo_utils import serialize

notifications_bp = Blueprint("notifications", __name__, url_prefix="/api/notifications")


def _svc():
    return current_app.extensions["notification_service"]


def _user():
    return current_app.extensions["alert_service"].user_id


@notifications_bp.get("")
def list_notifications():
    unread_only = request.args.get("unread", "").lower() in ("1", "true", "yes")
    items = _svc().list(_user(), unread_only)
    return jsonify({"notifications": serialize(items), "unread_count": _svc().unread_count(_user())})


@notifications_bp.post("/<notification_id>/read")
def mark_read(notification_id):
    if not _svc().mark_read(notification_id):
        raise AlertNotFoundError("Notification not found.")
    return jsonify({"id": notification_id, "is_read": True})


@notifications_bp.post("/read-all")
def mark_all_read():
    return jsonify({"updated": _svc().mark_all_read(_user())})
