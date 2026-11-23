"""MongoDB access for the `price_alerts` collection (Repository pattern)."""
from pymongo import ReturnDocument

from app.utils.mongo_utils import to_object_id, utcnow


class AlertRepository:
    COLLECTION = "price_alerts"

    def __init__(self, db):
        self.col = db[self.COLLECTION]
        self.col.create_index([("user_id", 1), ("stock_symbol", 1), ("is_triggered", 1)])

    def create(self, user_id, symbol, condition, target_price):
        now = utcnow()
        doc = {"user_id": user_id, "stock_symbol": symbol, "condition": condition,
               "target_price": target_price, "is_triggered": False, "triggered_at": None,
               "created_at": now, "updated_at": now}
        self.col.insert_one(doc)  # adds _id in place
        return doc

    def get(self, alert_id):
        oid = to_object_id(alert_id)
        return self.col.find_one({"_id": oid}) if oid else None

    def list(self, user_id, symbol=None, is_triggered=None):
        query = {"user_id": user_id}
        if symbol:
            query["stock_symbol"] = symbol
        if is_triggered is not None:
            query["is_triggered"] = is_triggered
        return list(self.col.find(query).sort("created_at", -1))

    def find_active_for_symbol(self, user_id, symbol):
        return list(self.col.find({
            "user_id": user_id,
            "stock_symbol": symbol,
            "is_triggered": False,
        }))

    def claim_trigger(self, alert_id, when):
        """Atomically flip is_triggered False -> True. Only ONE caller can win, which is what
        guarantees a single notification even with concurrent refreshes."""
        doc = self.col.find_one_and_update(
            {"_id": to_object_id(alert_id), "is_triggered": False},
            {"$set": {"is_triggered": True, "triggered_at": when, "updated_at": when}},
            return_document=ReturnDocument.AFTER)
        return doc is not None

    def release_trigger(self, alert_id):
        """Undo a claim (used if notification creation failed)."""
        return self.reset(alert_id)

    def reset(self, alert_id):
        oid = to_object_id(alert_id)
        if not oid:
            return False
        res = self.col.update_one({"_id": oid}, {"$set": {
            "is_triggered": False, "triggered_at": None, "updated_at": utcnow()}})
        return res.matched_count > 0

    def update(self, alert_id, fields):
        oid = to_object_id(alert_id)
        if not oid:
            return None
        fields = {**fields, "updated_at": utcnow()}
        return self.col.find_one_and_update({"_id": oid}, {"$set": fields},
                                            return_document=ReturnDocument.AFTER)

    def delete(self, alert_id):
        oid = to_object_id(alert_id)
        return bool(oid) and self.col.delete_one({"_id": oid}).deleted_count > 0
