"""MongoDB access for the `notifications` collection (Repository pattern)."""
from app.utils.mongo_utils import to_object_id, utcnow


class NotificationRepository:
    COLLECTION = "notifications"

    def __init__(self, db):
        self.col = db[self.COLLECTION]
        self.col.create_index([("user_id", 1), ("is_read", 1), ("timestamp", -1)])

    def create(self, user_id, alert_id, symbol, event_type, message, current_price,
               target_price, timestamp=None):
        doc = {"user_id": user_id, "alert_id": to_object_id(alert_id), "stock_symbol": symbol,
               "event_type": event_type, "message": message, "current_price": current_price,
               "target_price": target_price, "timestamp": timestamp or utcnow(), "is_read": False}
        self.col.insert_one(doc)
        return doc

    def list(self, user_id, unread_only=False, limit=100):
        query = {"user_id": user_id}
        if unread_only:
            query["is_read"] = False
        return list(self.col.find(query).sort("timestamp", -1).limit(limit))

    def count_unread(self, user_id):
        return self.col.count_documents({"user_id": user_id, "is_read": False})

    def mark_read(self, notification_id):
        oid = to_object_id(notification_id)
        if not oid:
            return False
        return self.col.update_one({"_id": oid}, {"$set": {"is_read": True}}).matched_count > 0

    def mark_all_read(self, user_id):
        return self.col.update_many({"user_id": user_id, "is_read": False},
                                    {"$set": {"is_read": True}}).modified_count
