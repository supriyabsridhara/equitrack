class WatchlistValidationError(ValueError):
    pass


class WatchlistDuplicateError(ValueError):
    pass


class WatchlistNotFoundError(LookupError):
    pass


class WatchlistService:
    def __init__(self, repository, stock_service):
        self.repository = repository
        self.stock_service = stock_service

    def add(self, user_id, symbol):
        symbol = str(symbol or "").strip().upper()
        if not symbol:
            raise WatchlistValidationError("Enter a stock symbol.")
        if not self.stock_service.symbol_exists(symbol):
            raise WatchlistValidationError(f"Unknown stock symbol: {symbol}.")
        item = self.repository.add(user_id, symbol)
        if item is None:
            raise WatchlistDuplicateError(f"{symbol} is already on your watchlist.")
        return item

    def list(self, user_id):
        items = self.repository.list(user_id)
        return [self._decorate(item) for item in items]

    def remove(self, user_id, item_id):
        if not self.repository.remove(user_id, item_id):
            raise WatchlistNotFoundError("Watchlist item not found.")

    def _decorate(self, item):
        symbol = item["stock_symbol"]
        details = self.stock_service.cached_stock(symbol)
        if details is None:
            stock = self.stock_service.repository.get_stock(symbol)
            details = {
                "symbol": symbol,
                "name": (stock or {}).get("name") or symbol,
                "exchange": (stock or {}).get("exchange") or "",
                "currency": (stock or {}).get("currency") or "INR",
            }
        return {**item, **details}
