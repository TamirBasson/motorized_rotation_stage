from __future__ import annotations

from dataclasses import dataclass
import logging
from threading import Lock
from typing import Callable, Literal
from uuid import uuid4

from pc_app.comm.models import TelemetryState


TelemetryCallback = Callable[[TelemetryState], None]
TelemetryPriority = Literal["high", "low"]
LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class TelemetrySubscription:
    subscription_id: str
    _unsubscribe: Callable[[str], None]

    def unsubscribe(self) -> None:
        self._unsubscribe(self.subscription_id)


@dataclass(frozen=True, slots=True)
class _Subscriber:
    priority: TelemetryPriority
    callback: TelemetryCallback


class TelemetryBus:
    """Distributes parsed telemetry updates to multiple subscribers."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._subscribers: dict[str, _Subscriber] = {}

    def subscribe(self, callback: TelemetryCallback, *, priority: TelemetryPriority = "high") -> TelemetrySubscription:
        if priority not in {"high", "low"}:
            raise ValueError("priority must be 'high' or 'low'")
        subscription_id = str(uuid4())
        with self._lock:
            self._subscribers[subscription_id] = _Subscriber(priority=priority, callback=callback)
        return TelemetrySubscription(subscription_id=subscription_id, _unsubscribe=self.unsubscribe)

    def unsubscribe(self, subscription_id: str) -> None:
        with self._lock:
            self._subscribers.pop(subscription_id, None)

    def publish(self, telemetry: TelemetryState) -> None:
        with self._lock:
            subscribers = list(self._subscribers.values())

        high_priority_callbacks = [subscriber.callback for subscriber in subscribers if subscriber.priority == "high"]
        low_priority_callbacks = [subscriber.callback for subscriber in subscribers if subscriber.priority == "low"]

        for callback in [*high_priority_callbacks, *low_priority_callbacks]:
            # One faulty subscriber must not break telemetry delivery for the rest.
            try:
                callback(telemetry)
            except Exception:
                LOGGER.exception("Telemetry subscriber callback failed")

    def subscriber_count(self) -> int:
        with self._lock:
            return len(self._subscribers)
