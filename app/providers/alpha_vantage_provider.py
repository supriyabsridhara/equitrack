import math
import os
from datetime import datetime, timezone

import requests

from app.providers.stock_data_provider import StockDataProvider


class StockDataError(RuntimeError):
    pass


class SymbolNotFoundError(LookupError):
    pass


class AlphaVantageProvider(StockDataProvider):
    BASE_URL = "https://www.alphavantage.co/query"
    TIMEOUT = 15

    def __init__(self, api_key=None, session=None):
        self.api_key = api_key or os.getenv("ALPHA_VANTAGE_API_KEY")
        self.session = session or requests.Session()

    def _get(self, params):
        if not self.api_key:
            raise StockDataError("Alpha Vantage API key is not configured.")
        try:
            response = self.session.get(
                self.BASE_URL,
                params={**params, "apikey": self.api_key},
                timeout=self.TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise StockDataError("The stock market provider is temporarily unavailable.") from exc

        if "Error Message" in data:
            raise SymbolNotFoundError(str(data["Error Message"]))
        if "Note" in data or "Information" in data:
            raise StockDataError("The stock market provider rate limit was reached. Please try again later.")
        return data

    @staticmethod
    def _parse_datetime(value):
        if not value:
            return datetime.now(timezone.utc)
        try:
            parsed = datetime.strptime(str(value), "%Y-%m-%d")
            return parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            try:
                parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
                return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
            except ValueError:
                return datetime.now(timezone.utc)

    def search_stocks(self, query):
        query = str(query or "").strip()
        if not query:
            return []
        data = self._get({"function": "SYMBOL_SEARCH", "keywords": query})
        matches = data.get("bestMatches") or []
        results = []
        for match in matches:
            symbol = str(match.get("1. symbol") or "").strip().upper()
            if not symbol:
                continue
            results.append({
                "symbol": symbol,
                "name": match.get("2. name") or symbol,
                "exchange": match.get("4. region") or match.get("3. type") or "",
                "currency": match.get("8. currency") or "USD",
            })
        return results

    def get_stock_details(self, symbol):
        symbol = str(symbol or "").strip().upper()
        if not symbol:
            raise SymbolNotFoundError("Enter a valid stock symbol.")
        search = self.search_stocks(symbol)
        match = next((item for item in search if item["symbol"] == symbol), None)
        quote = self._get({"function": "GLOBAL_QUOTE", "symbol": symbol})
        row = quote.get("Global Quote") or {}
        price = self._number(row.get("05. price"))
        previous = self._number(row.get("08. previous close"))
        if price is None or price <= 0:
            raise SymbolNotFoundError(f"No stock found for {symbol}.")
        market_time = self._parse_datetime(row.get("07. latest trading day"))
        return {
            "symbol": symbol,
            "name": (match or {}).get("name") or symbol,
            "exchange": (match or {}).get("exchange") or "",
            "currency": (match or {}).get("currency") or "USD",
            "last_price": price,
            "previous_close": previous,
            "price_timestamp": market_time,
            "data_source": "Alpha Vantage",
        }

    def get_latest_price(self, symbol, forced_price=None):
        if forced_price is not None:
            raise StockDataError("Price overrides are only available with the mock market-data provider.")
        details = self.get_stock_details(symbol)
        return {
            "symbol": details["symbol"],
            "price": details["last_price"],
            "previous_close": details["previous_close"],
            "market_time": details["price_timestamp"],
            "source": "Alpha Vantage",
        }

    def get_daily_history(self, symbol):
        symbol = str(symbol or "").strip().upper()
        data = self._get({"function": "TIME_SERIES_DAILY", "symbol": symbol})
        rows = data.get("Time Series (Daily)") or {}
        history = []
        for market_date, values in rows.items():
            close = self._number(values.get("4. close"))
            if close is not None:
                history.append({
                    "symbol": symbol,
                    "date": market_date,
                    "open": self._number(values.get("1. open")),
                    "high": self._number(values.get("2. high")),
                    "low": self._number(values.get("3. low")),
                    "close": close,
                    "volume": self._number(values.get("5. volume")),
                })
        history.sort(key=lambda item: item["date"], reverse=True)
        return history

    @staticmethod
    def _number(value):
        try:
            number = float(value)
            return number if math.isfinite(number) else None
        except (TypeError, ValueError):
            return None
