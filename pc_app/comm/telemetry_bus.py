from __future__ import annotations

from dataclasses import dataclass
import logging
from threading import Lock
from typing import Callable
from uuid import uuid4

from pc_app.comm.models import TelemetryState


TelemetryCallback = Callable[[TelemetryState], None]
LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class TelemetrySubscription:
    subscription_id: str
    _unsubscribe: Callable[[str], None]

    def unsubscribe(self) -> None:
        self._unsubscribe(self.subscription_id)


class TelemetryBus:
    """Distributes parsed telemetry updates to multiple subscribers."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._subscribers: dict[str, TelemetryCallback] = {}

    def subscribe(self, callback: TelemetryCallback) -> TelemetrySubscription:
        subscription_id = str(uuid4())
        with self._lock:
            self._subscribers[subscription_id] = callback
        return TelemetrySubscription(subscription_id=subscription_id, _unsubscribe=self.unsubscribe)

    def unsubscribe(self, subscription_id: str) -> None:
        with self._lock:
            self._subscribers.pop(subscription_id, None)

    def publish(self, telemetry: TelemetryState) -> None:
        with self._lock:
            subscribers = list(self._subscribers.values())

        for callback in subscribers:
            # One faulty subscriber must not break telemetry delivery for the rest.
            try:
                callback(telemetry)
            except Exception:
                LOGGER.exception("Telemetry subscriber callback failed")

    def subscriber_count(self) -> int:
        with self._lock:
            return len(self._subscribers)
