"""Serves the single-page UI plus liveness/readiness probes."""
from pathlib import Path

from flask import Blueprint, current_app, jsonify, send_from_directory

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"

frontend_bp = Blueprint("frontend", __name__, static_folder=str(FRONTEND_DIR / "static"),
                        static_url_path="/assets")


@frontend_bp.get("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@frontend_bp.get("/health")
def health():
    """Liveness: the process is up (used by Docker HEALTHCHECK and the K8s livenessProbe)."""
    return jsonify({"status": "ok"})


@frontend_bp.get("/ready")
def ready():
    """Readiness: MongoDB answers (used by the K8s readinessProbe)."""
    try:
        current_app.extensions["mongo_db"].command("ping")
        return jsonify({"status": "ready", "database": True})
    except Exception:  # noqa: BLE001
        return jsonify({"status": "unavailable", "database": False}), 503
