from pymongo import DESCENDING

from app.utils.mongo_utils import utcnow


class StockRepository:
    def __init__(self, db):
        self.db = db
        self.stocks = db["stocks"]
        self.snapshots = db["price_snapshots"]
        self.stocks.create_index([("symbol", 1)], unique=True)
        self.snapshots.create_index([("symbol", 1), ("market_time", 1)], unique=True)
        self.snapshots.create_index([("symbol", 1), ("fetched_at", DESCENDING)])

    def upsert_stock(self, details):
        now = utcnow()
        doc = {
            "symbol": str(details["symbol"]).strip().upper(),
            "name": details.get("name") or str(details["symbol"]).strip().upper(),
            "exchange": details.get("exchange") or "",
            "currency": details.get("currency") or "INR",
            "updated_at": now,
        }
        self.stocks.update_one({"symbol": doc["symbol"]}, {"$set": doc, "$setOnInsert": {"created_at": now}}, upsert=True)
        return self.stocks.find_one({"symbol": doc["symbol"]})

    def get_stock(self, symbol):
        return self.stocks.find_one({"symbol": str(symbol).strip().upper()})

    def save_snapshot(self, symbol, price, market_time, source):
        now = utcnow()
        doc = {
            "symbol": str(symbol).strip().upper(),
            "price": float(price),
            "market_time": market_time,
            "fetched_at": now,
            "source": source or "Unknown",
        }
        self.snapshots.update_one(
            {"symbol": doc["symbol"], "market_time": market_time},
            {"$set": doc},
            upsert=True,
        )
        return doc

    def latest_snapshot(self, symbol):
        return self.snapshots.find_one(
            {"symbol": str(symbol).strip().upper()},
            sort=[("market_time", DESCENDING), ("fetched_at", DESCENDING)],
        )
