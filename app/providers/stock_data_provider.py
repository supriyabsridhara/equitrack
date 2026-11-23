from abc import ABC, abstractmethod


class StockDataProvider(ABC):
    @abstractmethod
    def search_stocks(self, query):
        raise NotImplementedError

    @abstractmethod
    def get_stock_details(self, symbol):
        raise NotImplementedError

    @abstractmethod
    def get_latest_price(self, symbol, forced_price=None):
        raise NotImplementedError

    @abstractmethod
    def get_daily_history(self, symbol):
        raise NotImplementedError
