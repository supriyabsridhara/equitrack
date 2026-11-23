import math


class PortfolioValidationError(ValueError):
    pass


class PortfolioService:
    def __init__(self, holding_repo, transaction_repo, stock_service, user_id):
        self.holdings = holding_repo
        self.transaction_repo = transaction_repo
        self.stock_service = stock_service
        self.user_id = user_id

    def buy(self, symbol, quantity, price):
        symbol = self._validate_symbol(symbol)
        quantity = self._validate_quantity(quantity)
        price = self._validate_price(price)
        if not self.stock_service.symbol_exists(symbol):
            raise PortfolioValidationError(f"Unknown stock symbol: {symbol}.")

        holding = self.holdings.get(self.user_id, symbol)
        old_quantity = int(holding["quantity"]) if holding else 0
        old_cost = float(holding["total_cost_basis"]) if holding else 0.0
        realized = float(holding["realized_profit_loss"]) if holding else 0.0
        new_quantity = old_quantity + quantity
        new_cost = old_cost + quantity * price
        average = new_cost / new_quantity
        self.holdings.save(self.user_id, symbol, new_quantity, average, new_cost, realized)
        return self.transaction_repo.create(self.user_id, symbol, "BUY", quantity, price)

    def sell(self, symbol, quantity, price):
        symbol = self._validate_symbol(symbol)
        quantity = self._validate_quantity(quantity)
        price = self._validate_price(price)
        if not self.stock_service.symbol_exists(symbol):
            raise PortfolioValidationError(f"Unknown stock symbol: {symbol}.")

        holding = self.holdings.get(self.user_id, symbol)
        if not holding:
            raise PortfolioValidationError(f"You do not own any shares of {symbol}.")
        owned = int(holding["quantity"])
        if quantity > owned:
            raise PortfolioValidationError(f"You hold {owned} shares of {symbol}; cannot sell {quantity}.")

        old_cost = float(holding["total_cost_basis"])
        average = float(holding["average_purchase_price"])
        if average <= 0 and owned:
            average = old_cost / owned
        realized = float(holding["realized_profit_loss"])
        trade_realized = (price - average) * quantity
        realized += trade_realized
        remaining = owned - quantity
        remaining_cost = 0.0 if remaining == 0 else old_cost - average * quantity
        remaining_average = remaining_cost / remaining if remaining else 0.0
        self.holdings.save(self.user_id, symbol, remaining, remaining_average,
                           remaining_cost, realized)
        return self.transaction_repo.create(
            self.user_id, symbol, "SELL", quantity, price, trade_realized
        )

    def summary(self):
        holdings = []
        total_invested = 0.0
        current_value = 0.0
        for holding in self.holdings.list(self.user_id):
            symbol = holding["symbol"]
            quantity = int(holding["quantity"])
            cost = float(holding["total_cost_basis"])
            avg = float(holding["average_purchase_price"])
            stock = self.stock_service.cached_stock(symbol)
            current_price = stock["last_price"] if stock and stock["last_price"] is not None else None
            if current_price is None:
                current_price = 0.0
            value = round(quantity * float(current_price), 4)
            unrealized = round(value - cost, 4)
            realized = float(holding["realized_profit_loss"])
            holdings.append({
                "stock_symbol": symbol,
                "quantity": quantity,
                "total_cost_basis": round(cost, 4),
                "average_purchase_price": round(avg, 4),
                "current_price": float(current_price),
                "current_value": value,
                "unrealized_profit_loss": unrealized,
                "realized_profit_loss": realized,
                "currency": (stock or {}).get("currency") or "INR",
                "price_timestamp": (stock or {}).get("price_timestamp"),
                "data_source": (stock or {}).get("data_source") or "Unknown",
            })
            total_invested += cost
            current_value += value

        unrealized = round(current_value - total_invested, 4)
        realized = self.holdings.realized_profit_loss(self.user_id)
        return_percentage = round(unrealized / total_invested * 100, 2) if total_invested else 0.0
        return {
            "holdings": holdings,
            "summary": {
                "total_invested": round(total_invested, 4),
                "current_value": round(current_value, 4),
                "unrealized_profit_loss": unrealized,
                "realized_profit_loss": realized,
                "return_percentage": return_percentage,
            },
        }

    def transactions(self):
        return self.transaction_repo.list(self.user_id)

    @staticmethod
    def _validate_symbol(value):
        symbol = str(value or "").strip().upper()
        if not symbol:
            raise PortfolioValidationError("Enter a stock symbol.")
        return symbol

    @staticmethod
    def _validate_quantity(value):
        if isinstance(value, bool):
            raise PortfolioValidationError("Quantity must be a whole number greater than zero.")
        try:
            quantity = int(value)
        except (TypeError, ValueError):
            raise PortfolioValidationError("Quantity must be a whole number greater than zero.") from None
        if isinstance(value, float) and not value.is_integer():
            raise PortfolioValidationError("Quantity must be a whole number greater than zero.")
        if quantity <= 0:
            raise PortfolioValidationError("Quantity must be a whole number greater than zero.")
        return quantity

    @staticmethod
    def _validate_price(value):
        if isinstance(value, bool):
            raise PortfolioValidationError("Price must be greater than zero.")
        try:
            price = float(value)
        except (TypeError, ValueError):
            raise PortfolioValidationError("Price must be greater than zero.") from None
        if not math.isfinite(price) or price <= 0:
            raise PortfolioValidationError("Price must be greater than zero.")
        return round(price, 4)
