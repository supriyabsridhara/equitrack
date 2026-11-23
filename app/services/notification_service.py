"""Turns price events into stored notifications. Subscribed to the EventDispatcher."""
from app.repositories.notification_repository import NotificationRepository

CURRENCY_SYMBOLS = {"INR": "₹", "USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥"}


def format_money(amount, currency):
    symbol = CURRENCY_SYMBOLS.get(currency, f"{currency} " if currency else "")
    return f"{symbol}{amount:,.2f}"


class NotificationService:
    def __init__(self, repository: NotificationRepository, currency_lookup=None, default_currency="INR"):
        self.repo = repository
        self._lookup = currency_lookup or (lambda symbol: None)
        self.default_currency = default_currency

    def handle_event(self, event):
        """Dispatcher callback: create exactly one notification for the event."""
        currency = self._lookup(event.stock_symbol) or self.default_currency
        current = format_money(event.current_price, currency)
        if hasattr(event, "threshold_price"):
            target = event.threshold_price
            message = (f"{event.stock_symbol} fell below your threshold of "
                       f"{format_money(target, currency)} (now {current})")
        else:
            target = event.target_price
            message = (f"{event.stock_symbol} reached your target of "
                       f"{format_money(target, currency)} (now {current})")
        return self.repo.create(event.user_id, event.alert_id, event.stock_symbol, event.event_type,
                                message, event.current_price, target, event.occurred_at)

    def list(self, user_id, unread_only=False):
        return self.repo.list(user_id, unread_only)

    def unread_count(self, user_id):
        return self.repo.count_unread(user_id)

    def mark_read(self, notification_id):
        return self.repo.mark_read(notification_id)

    def mark_all_read(self, user_id):
        return self.repo.mark_all_read(user_id)
