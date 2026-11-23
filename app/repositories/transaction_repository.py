from pymongo import DESCENDING

from app.utils.mongo_utils import utcnow


class TransactionRepository:
    def __init__(self, db):
        self.col = db["portfolio_transactions"]
        self.col.create_index([("user_id", 1), ("timestamp", DESCENDING)])
        self.col.create_index([("user_id", 1), ("stock_symbol", 1)])

    def create(self, user_id, symbol, transaction_type, quantity, price,
               realized_profit_loss=0.0, timestamp=None):
        doc = {
            "user_id": user_id,
            "stock_symbol": symbol,
            "transaction_type": transaction_type,
            "quantity": int(quantity),
            "price": float(price),
            "total_amount": round(int(quantity) * float(price), 4),
            "realized_profit_loss": round(float(realized_profit_loss), 4),
            "timestamp": timestamp or utcnow(),
        }
        self.col.insert_one(doc)
        return doc

    def list(self, user_id):
        return list(self.col.find({"user_id": user_id}).sort("timestamp", DESCENDING))
