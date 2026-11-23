import math
import random
from datetime import datetime, timezone

from app.providers.stock_data_provider import StockDataProvider


class MockSymbolNotFoundError(LookupError):
    pass


class MockStockDataProvider(StockDataProvider):
    STOCKS = {
        "AAPL": {"name": "Apple Inc.", "exchange": "NASDAQ", "currency": "USD", "price": 185.50},
        "INFY": {"name": "Infosys Ltd", "exchange": "NSE", "currency": "INR", "price": 1620.0},
        "TCS": {"name": "Tata Consultancy Services", "exchange": "NSE", "currency": "INR", "price": 3200.0},
        "RELIANCE": {"name": "Reliance Industries", "exchange": "NSE", "currency": "INR", "price": 1450.0},
        "MSFT": {"name": "Microsoft Corporation", "exchange": "NASDAQ", "currency": "USD", "price": 425.0},
    }

    def __init__(self, catalog=None, rng=None):
        self.catalog = dict(catalog or self.STOCKS)
        self._prices = {symbol: float(row["price"]) for symbol, row in self.catalog.items()}
        self._previous = dict(self._prices)
        self.rng = rng or random

    def symbol_exists(self, symbol):
        return str(symbol or "").strip().upper() in self.catalog

    def search_stocks(self, query):
        needle = str(query or "").strip().upper()
        if not needle:
            return []
        results = []
        for symbol, row in self.catalog.items():
            if needle in symbol or needle in str(row["name"]).upper():
                results.append({
                    "symbol": symbol,
                    "name": row["name"],
                    "exchange": row["exchange"],
                    "currency": row["currency"],
                })
        return results

    def get_stock_details(self, symbol):
        symbol = str(symbol or "").strip().upper()
        if symbol not in self.catalog:
            raise MockSymbolNotFoundError(f"No stock found for {symbol}.")
        row = self.catalog[symbol]
        price = self._prices[symbol]
        return {
            "symbol": symbol,
            "name": row["name"],
            "exchange": row["exchange"],
            "currency": row["currency"],
            "last_price": price,
            "previous_close": self._previous[symbol],
            "price_timestamp": datetime.now(timezone.utc),
            "data_source": "Mock provider",
        }

    def get_latest_price(self, symbol, forced_price=None):
        symbol = str(symbol or "").strip().upper()
        if symbol not in self.catalog:
            raise MockSymbolNotFoundError(f"No stock found for {symbol}.")
        previous = self._prices[symbol]
        if forced_price is not None:
            if isinstance(forced_price, bool):
                raise ValueError("Price must be greater than zero.")
            price = float(forced_price)
        else:
            price = round(previous * (1 + self.rng.uniform(-0.015, 0.015)), 2)
        if not math.isfinite(price) or price <= 0:
            raise ValueError("Price must be greater than zero.")
        now = datetime.now(timezone.utc)
        self._previous[symbol] = previous
        self._prices[symbol] = price
        return {
            "symbol": symbol,
            "price": price,
            "previous_close": previous,
            "market_time": now,
            "source": "Mock provider",
        }

    def get_daily_history(self, symbol):
        details = self.get_stock_details(symbol)
        return [{"symbol": symbol, "date": datetime.now(timezone.utc).date().isoformat(),
                 "close": details["last_price"]}]
