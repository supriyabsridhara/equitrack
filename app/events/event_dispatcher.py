"""Minimal synchronous publish/subscribe dispatcher."""
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


class EventDispatcher:
    def __init__(self):
        self._subscribers = defaultdict(list)

    def subscribe(self, event_cls, handler):
        if handler not in self._subscribers[event_cls]:
            self._subscribers[event_cls].append(handler)

    def unsubscribe(self, event_cls, handler):
        if handler in self._subscribers.get(event_cls, []):
            self._subscribers[event_cls].remove(handler)

    def publish(self, event, strict=False):
        """Call every handler subscribed to the event's class (or a base class).

        Returns the list of handler return values. A failing handler never stops the
        others; with strict=True the first error is re-raised after all handlers ran.
        """
        results, first_error = [], None
        for cls in type(event).__mro__:
            for handler in list(self._subscribers.get(cls, [])):
                try:
                    results.append(handler(event))
                except Exception as exc:  # noqa: BLE001 - isolate handlers from each other
                    logger.exception("Handler %s failed for %s", handler, type(event).__name__)
                    first_error = first_error or exc
        if strict and first_error:
            raise first_error
        return results
