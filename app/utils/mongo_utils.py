"""Small helpers shared by Member 2's repositories, services and routes."""
from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId


def utcnow():
    return datetime.now(timezone.utc)


def to_object_id(value):
    """Return an ObjectId, or None when the value is not a valid id."""
    if isinstance(value, ObjectId):
        return value
    try:
        return ObjectId(str(value))
    except (InvalidId, TypeError):
        return None


def serialize(value):
    """Make Mongo documents JSON-safe: ObjectId -> str, datetime -> ISO-8601 (UTC, 'Z')."""
    if isinstance(value, dict):
        out = {k: serialize(v) for k, v in value.items()}
        if "_id" in out:
            out["id"] = out["_id"]
        return out
    if isinstance(value, list):
        return [serialize(v) for v in value]
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    return value
