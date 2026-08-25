"""Deduplicator for Alertmanager notifications."""

import collections
from dataclasses import dataclass
from alertmanager import Notification, Alert

def _hash_alert(alert: Alert) -> int:
    """Used to reidentify the same alert in a followup notification."""
    return hash((
        alert.status.value,
        frozenset(alert.labels.items()),
        frozenset(alert.annotations.items()),
        alert.starts_at,
        alert.ends_at,
        alert.generator_url,
        alert.fingerprint
    ))

def _hash_notification(notification: Notification) -> int:
    """Used to determine idempotency when receiving retries from alertmanager (we treat changed data inside notifications as new notifications)."""
    return hash((
        notification.group_key,
        notification.status.value,
        notification.receiver,
        tuple(_hash_alert(alert) for alert in notification.alerts)
    ))

@dataclass
class DuplicationCheckResponse:
    """Answer to a deduplication check for a notification."""

    is_duplicate: bool
    """Whether the notification is a duplicate of a previously received notification."""
    hash_key: str
    """The deduplication key (ie. hash of the notification) in serialized form (useful for logging)"""

    def __init__(self, is_duplicate: bool, hash_key: str):
        self.is_duplicate = is_duplicate
        self.hash_key = hash_key

class Deduplicator:
    """Deduplicator for Alertmanager notifications."""

    _sent_notifications_dedup_cache: collections.deque[int]
    """
    Cache the groupKeys of received notifications to avoid sending duplicates.
    A deque auto-prunes oldest entries, so no need to worry about memory usage.
    """

    def __init__(self, maxlen: int = 100):
        self._sent_notifications_dedup_cache = collections.deque(maxlen=maxlen)
        self._last_key = 0

    def check(self, notification: Notification) -> DuplicationCheckResponse:
        """Check if the given dedup_key has already been seen."""
        dedup_key = self._key(notification)
        if dedup_key in self._sent_notifications_dedup_cache:
            return DuplicationCheckResponse(True, str(dedup_key))
        return DuplicationCheckResponse(False, str(dedup_key))

    def add(self, notification: Notification) -> None:
        """Add the given notification's dedup_key to the deduplication cache."""
        dedup_key = self._key(notification)
        self._sent_notifications_dedup_cache.append(dedup_key)

    def _key(self, notification: Notification) -> int:
        """Get the deduplication key for this notification."""
        return _hash_notification(notification)
