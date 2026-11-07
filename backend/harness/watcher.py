"""Polls the live alert feeds (src/live_alerts.py) on a timer and tells the server when a NEW alert appears."""

import logging
import threading
from collections.abc import Callable

logger = logging.getLogger(__name__)

Alert = dict
Fetch = Callable[[], list[Alert]]


class AlertWatcher:
    """Keeps the latest alerts for the website and reports each alert id once, so one event reruns the forecast once."""

    def __init__(self, fetch: Fetch, on_new: Callable[[list[Alert]], None], poll_seconds: int) -> None:
        self._fetch = fetch
        self._on_new = on_new
        self.poll_seconds = poll_seconds
        self._lock = threading.Lock()
        self._alerts: list[Alert] = []
        self._seen: set[str] = set()

    def snapshot(self) -> list[Alert]:
        """The alerts of the latest poll."""
        with self._lock:
            return list(self._alerts)

    def poll(self) -> list[Alert]:
        """One poll: store the latest alerts and return those whose id has not been seen before."""
        try:
            alerts = self._fetch()
        except Exception:  # any feed failure must leave the watcher alive; the cause is logged
            logger.exception("alert feeds failed")
            alerts = []
        with self._lock:
            self._alerts = alerts
            new = [alert for alert in alerts if alert["id"] not in self._seen]
            self._seen.update(alert["id"] for alert in alerts)
        return new

    def step(self) -> None:
        """One timer tick: poll, and hand new alerts to the callback (whose failure must not stop the watcher)."""
        new = self.poll()
        if not new:
            return
        try:
            self._on_new(new)
        except Exception:  # same reason: the watcher outlives a failing callback
            logger.exception("reacting to new alerts failed")

    def run(self, stop: threading.Event) -> None:
        """Seed with a first poll (existing alerts are not news), then poll every poll_seconds until `stop` is set."""
        self.poll()
        while not stop.wait(self.poll_seconds):
            self.step()
