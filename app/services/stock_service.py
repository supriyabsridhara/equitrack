import math

from app.providers.alpha_vantage_provider import SymbolNotFoundError as AlphaSymbolNotFoundError
from app.providers.alpha_vantage_provider import StockDataError
from app.providers.mock_stock_data_provider import MockSymbolNotFoundError
from app.utils.mongo_utils import utcnow


class StockValidationError(ValueError):
    pass


class StockNotFoundError(LookupError):
    pass


class StockProviderUnavailableError(RuntimeError):
    pass


class StockService:
    def __init__(self, repository, provider):
        self.repository = repository
        self.provider = provider

    def symbol_exists(self, symbol):
        symbol = str(symbol or "").strip().upper()
        if not symbol:
            return False
        if hasattr(self.provider, "symbol_exists"):
            return bool(self.provider.symbol_exists(symbol))
        try:
            return self.provider.get_stock_details(symbol) is not None
        except (LookupError, StockDataError):
            return False

    def search(self, query):
        query = str(query or "").strip()
        if not query:
            raise StockValidationError("Enter a ticker symbol to search.")
        if hasattr(self.provider, "symbol_exists") and len(query) <= 15:
            mock_results = self.provider.search_stocks(query)
            if mock_results:
                return mock_results
        results = self.provider.search_stocks(query)
        for item in results:
            self.repository.upsert_stock(item)
        return results

    def get_details(self, symbol):
        symbol = str(symbol or "").strip().upper()
        if not symbol:
            raise StockValidationError("Enter a valid stock symbol.")
        try:
            details = self.provider.get_stock_details(symbol)
        except (AlphaSymbolNotFoundError, MockSymbolNotFoundError) as exc:
            raise StockNotFoundError(str(exc)) from exc
        except StockDataError:
            raise
        stored = self.repository.upsert_stock(details)
        return self._format_stock(details, stored)

    def refresh_price(self, symbol, forced_price=None):
        symbol = str(symbol or "").strip().upper()
        try:
            data = self.provider.get_latest_price(symbol, forced_price)
        except (AlphaSymbolNotFoundError, MockSymbolNotFoundError) as exc:
            raise StockNotFoundError(str(exc)) from exc

        price = float(data["price"])
        if not math.isfinite(price) or price <= 0:
            raise StockValidationError("The provider returned an invalid stock price.")
        market_time = data.get("market_time") or utcnow()
        source = data.get("source") or "Unknown"
        snapshot = self.repository.save_snapshot(symbol, price, market_time, source)
        details = self.provider.get_stock_details(symbol)
        self.repository.upsert_stock(details)
        return {
            "symbol": symbol,
            "name": details.get("name"),
            "exchange": details.get("exchange"),
            "currency": details.get("currency"),
            "last_price": price,
            "previous_close": data.get("previous_close"),
            "price_timestamp": snapshot["market_time"],
            "data_source": source,
            "cached": False,
        }

    def cached_stock(self, symbol):
        symbol = str(symbol or "").strip().upper()
        stock = self.repository.get_stock(symbol)
        snapshot = self.repository.latest_snapshot(symbol)
        if stock is None or snapshot is None:
            return None
        return self._format_stock({
            "symbol": symbol,
            "name": stock.get("name"),
            "exchange": stock.get("exchange"),
            "currency": stock.get("currency"),
            "last_price": snapshot["price"],
            "previous_close": None,
            "price_timestamp": snapshot["market_time"],
            "data_source": snapshot["source"],
        }, stock, cached=True)

    def latest_known_price(self, symbol):
        snapshot = self.repository.latest_snapshot(symbol)
        if snapshot:
            return float(snapshot["price"])
        return None

    @staticmethod
    def _format_stock(details, stored=None, cached=False):
        return {
            "symbol": str(details["symbol"]).upper(),
            "name": details.get("name") or (stored or {}).get("name") or str(details["symbol"]).upper(),
            "exchange": details.get("exchange") or (stored or {}).get("exchange") or "",
            "currency": details.get("currency") or (stored or {}).get("currency") or "INR",
            "last_price": details.get("last_price"),
            "previous_close": details.get("previous_close"),
            "price_timestamp": details.get("price_timestamp"),
            "data_source": details.get("data_source") or "Unknown",
            "cached": cached,
        }
