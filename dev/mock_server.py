"""Stand-in for Member 1's backend so the UI and alerts can be built and demoed alone.

It implements the exact API contract in docs/MEMBER1_INTEGRATION.md with in-memory data and an
in-memory MongoDB (mongomock). Run:  python -m dev.mock_server   ->  http://localhost:5000
POST /api/stocks/<SYM>/refresh accepts {"price": 2005} to force a price (demo/test only).
"""
import itertools
import random
from datetime import datetime, timezone

import mongomock
from flask import Flask, jsonify, request

from app.integration import init_alerts_and_ui, notify_price_update

STOCKS = {"AAPL": ("Apple Inc.", "NASDAQ", "USD", 185.50), "INFY": ("Infosys Ltd", "NSE", "INR", 1620.0),
          "TCS": ("Tata Consultancy Services", "NSE", "INR", 3200.0),
          "RELIANCE": ("Reliance Industries", "NSE", "INR", 1450.0)}


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def create_mock_app(db=None):
    app = Flask(__name__)
    db = db if db is not None else mongomock.MongoClient()["equitrack"]
    for sym, (name, exch, cur, _) in STOCKS.items():
        db.stocks.update_one({"symbol": sym}, {"$set": {"name": name, "currency": cur}}, upsert=True)
    app.extensions["mongo_db"] = db
    st = {"price": {s: v[3] for s, v in STOCKS.items()}, "prev": {s: v[3] for s, v in STOCKS.items()},
          "ts": {s: _now() for s in STOCKS}, "watch": {}, "txns": [], "hold": {}, "ids": itertools.count(1)}

    def err(msg, code=400):
        return jsonify({"error": msg}), code

    def stock(sym):
        name, exch, cur, _ = STOCKS[sym]
        return {"symbol": sym, "name": name, "exchange": exch, "currency": cur,
                "last_price": st["price"][sym], "previous_close": st["prev"][sym],
                "price_timestamp": st["ts"][sym], "data_source": "Mock provider"}

    def sym_or_none(raw):
        sym = str(raw or "").strip().upper()
        return sym if sym in STOCKS else None

    @app.get("/api/stocks")
    def search():
        q = request.args.get("q", "").strip().upper()
        if not q:
            return err("Enter a ticker symbol to search.")
        hits = [{"symbol": s, "name": v[0], "exchange": v[1], "currency": v[2]}
                for s, v in STOCKS.items() if q in s or q in v[0].upper()]
        return jsonify({"results": hits})

    @app.get("/api/stocks/<symbol>")
    def details(symbol):
        sym = sym_or_none(symbol)
        return jsonify(stock(sym)) if sym else err(f"No stock found for {symbol.upper()}.", 404)

    @app.post("/api/stocks/<symbol>/refresh")
    def refresh(symbol):
        sym = sym_or_none(symbol)
        if not sym:
            return err(f"No stock found for {symbol.upper()}.", 404)
        forced = (request.get_json(silent=True) or {}).get("price")
        new = float(forced) if forced else round(st["price"][sym] * (1 + random.uniform(-.015, .015)), 2)
        st["prev"][sym], st["price"][sym], st["ts"][sym] = st["price"][sym], new, _now()
        out = stock(sym)
        out["triggered_alerts"] = notify_price_update(sym, new, st["prev"][sym], "Mock provider", datetime.now(timezone.utc))
        return jsonify(out)

    @app.get("/api/watchlist")
    def watch_list():
        return jsonify({"watchlist": [{**w, **stock(w["stock_symbol"])} for w in st["watch"].values()]})

    @app.post("/api/watchlist")
    def watch_add():
        sym = sym_or_none((request.get_json(silent=True) or {}).get("stock_symbol"))
        if not sym:
            return err("Unknown stock symbol.")
        if any(w["stock_symbol"] == sym for w in st["watch"].values()):
            return err(f"{sym} is already on your watchlist.", 409)
        wid = str(next(st["ids"]))
        st["watch"][wid] = {"_id": wid, "id": wid, "stock_symbol": sym, "added_at": _now()}
        return jsonify(st["watch"][wid]), 201

    @app.delete("/api/watchlist/<wid>")
    def watch_del(wid):
        return jsonify({"deleted": True}) if st["watch"].pop(wid, None) else err("Watchlist item not found.", 404)

    def trade(kind):
        d = request.get_json(silent=True) or {}
        sym = sym_or_none(d.get("stock_symbol"))
        try:
            qty, price = int(d.get("quantity")), float(d.get("price"))
        except (TypeError, ValueError):
            return err("Quantity must be a whole number and price a number.")
        if not sym:
            return err("Unknown stock symbol.")
        if qty <= 0 or price <= 0:
            return err("Quantity and price must be greater than zero.")
        h = st["hold"].setdefault(sym, {"quantity": 0, "cost": 0.0, "realized": 0.0})
        if kind == "BUY":
            h["quantity"] += qty
            h["cost"] += qty * price
        else:
            if qty > h["quantity"]:
                return err(f"You hold {h['quantity']} shares of {sym}; cannot sell {qty}.")
            avg = h["cost"] / h["quantity"]
            h["realized"] += (price - avg) * qty
            h["cost"] -= avg * qty
            h["quantity"] -= qty
        t = {"_id": str(next(st["ids"])), "stock_symbol": sym, "transaction_type": kind, "quantity": qty,
             "price": price, "total_amount": round(qty * price, 2), "timestamp": _now()}
        st["txns"].insert(0, t)
        return jsonify(t), 201

    app.add_url_rule("/api/portfolio/buy", "buy", lambda: trade("BUY"), methods=["POST"])
    app.add_url_rule("/api/portfolio/sell", "sell", lambda: trade("SELL"), methods=["POST"])

    @app.get("/api/transactions")
    def txns():
        return jsonify({"transactions": st["txns"]})

    @app.get("/api/portfolio")
    def portfolio():
        rows, inv, val, real = [], 0.0, 0.0, 0.0
        for sym, h in st["hold"].items():
            real += h["realized"]
            if h["quantity"] == 0:
                continue
            cur = st["price"][sym]
            cv = round(h["quantity"] * cur, 2)
            rows.append({"stock_symbol": sym, "quantity": h["quantity"], "total_cost_basis": round(h["cost"], 2),
                         "average_purchase_price": round(h["cost"] / h["quantity"], 2), "current_price": cur,
                         "current_value": cv, "unrealized_profit_loss": round(cv - h["cost"], 2),
                         "realized_profit_loss": round(h["realized"], 2), "currency": STOCKS[sym][2],
                         "price_timestamp": st["ts"][sym], "data_source": "Mock provider"})
            inv, val = inv + h["cost"], val + cv
        return jsonify({"holdings": rows, "summary": {
            "total_invested": round(inv, 2), "current_value": round(val, 2),
            "unrealized_profit_loss": round(val - inv, 2), "realized_profit_loss": round(real, 2),
            "return_percentage": round((val - inv) / inv * 100, 2) if inv else 0.0}})

    init_alerts_and_ui(app)
    return app


if __name__ == "__main__":
    create_mock_app().run(host="0.0.0.0", port=5000, debug=True)
