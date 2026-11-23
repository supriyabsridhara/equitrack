from pymongo import DESCENDING
from pymongo.errors import DuplicateKeyError

from app.utils.mongo_utils import to_object_id, utcnow


class WatchlistError(Exception):
    pass


class WatchlistRepository:
    def __init__(self, db):
        self.col = db["watchlist_items"]
        self.col.create_index([("user_id", 1), ("stock_symbol", 1)], unique=True)
        self.col.create_index([("user_id", 1), ("added_at", DESCENDING)])

    def exists(self, user_id, symbol):
        return self.col.count_documents({"user_id": user_id, "stock_symbol": symbol}) > 0

    def add(self, user_id, symbol):
        doc = {"user_id": user_id, "stock_symbol": symbol, "added_at": utcnow()}
        try:
            result = self.col.insert_one(doc)
        except DuplicateKeyError:
            return None
        doc["_id"] = result.inserted_id
        return doc

    def list(self, user_id):
        return list(self.col.find({"user_id": user_id}).sort("added_at", DESCENDING))

    def remove(self, user_id, item_id):
        oid = to_object_id(item_id)
        if oid is None:
            return False
        result = self.col.delete_one({"_id": oid, "user_id": user_id})
        return result.deleted_count > 0
