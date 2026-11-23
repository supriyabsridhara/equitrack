from pymongo import ASCENDING

from app.utils.mongo_utils import utcnow


class PortfolioRepository:
    def __init__(self, db):
        self.col = db["portfolio_holdings"]
        self.col.create_index([("user_id", 1), ("symbol", 1)], unique=True)

    def get(self, user_id, symbol):
        return self.col.find_one({"user_id": user_id, "symbol": symbol})

    def list(self, user_id, include_zero=False):
        query = {"user_id": user_id}
        if not include_zero:
            query["quantity"] = {"$gt": 0}
        return list(self.col.find(query).sort("symbol", ASCENDING))

    def save(self, user_id, symbol, quantity, average_price, total_cost_basis,
             realized_profit_loss=0.0):
        now = utcnow()
        doc = {
            "user_id": user_id,
            "symbol": symbol,
            "quantity": int(quantity),
            "average_purchase_price": round(float(average_price), 4),
            "total_cost_basis": round(float(total_cost_basis), 4),
            "realized_profit_loss": round(float(realized_profit_loss), 4),
            "updated_at": now,
        }
        self.col.update_one(
            {"user_id": user_id, "symbol": symbol},
            {"$set": doc, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )
        return self.get(user_id, symbol)

    def realized_profit_loss(self, user_id):
        total = 0.0
        for holding in self.list(user_id, include_zero=True):
            total += float(holding.get("realized_profit_loss") or 0)
        return round(total, 4)
