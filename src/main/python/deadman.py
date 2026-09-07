"""
    The 'deadman switch' is a technique to tell quietness and silence apart:
    Is the sender dead and cannot send alerts, or is it just not sending alerts,
    because there are none?

    We handle two deadman switches: one for the forwarder itself, and one for alertmanager.

    The forwarder deadman switch is implemented by sending a periodic
    email to the configured recipient.
    They have to monitor these downstream to see whether the forwarder is maybe down.

    The alertmanager deadman switch is implemented by a specific alertname in Alertmanager,
    which we expect to receive periodically.
    It is usually called "Watchdog" and configured in prometheus such that it
    always fires -- alertmanager will then need to be
    configured with an adequate route and `repeat_interval` to send it to this forwarder periodically.
    The forwarder itself will have a timeout for this alertname and escalate to the configured
    recipient if it does not receive **any** webhook in time.
"""

from collections.abc import Callable
from logging import Logger
import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.base import BaseScheduler

class Deadman:
    """Implements both the forwarder- and alertmanager- deadman-switches."""

    last_alertmanager_checkin_timestamp: datetime.datetime
    """When alertmanager checked in last time (via *any* notification)."""
    alertmanager_deadman_timeout: datetime.timedelta
    """How long to wait for alertmanager to check in before escalating."""
    alertmanager_deadman_interval: datetime.timedelta
    """How long to wait between sending consecutive alertmanager deadman emails (if alertmanager is still down)."""
    alertmanager_deadman_last_sent: datetime.datetime | None = None
    """The timestamp of the last alertmanager deadman email sent."""
    alertmanager_deadman_inhibition_alert_label_filter: dict[str, str]
    """Labels to identify the deadman-inhibition alert (empty disables the filter)."""

    forwarder_deadman_interval: datetime.timedelta
    """The interval at which to send out deadman-switch emails."""
    forwarder_deadman_at_start: bool
    """Whether to send a deadman-switch email immediately at startup."""
    forwarder_deadman_last_sent: datetime.datetime | None = None
    """The timestamp of the last deadman-switch email sent."""

    logger: Logger

    def __init__(
        self,
        alertmanager_deadman_timeout: datetime.timedelta,
        alertmanager_deadman_interval: datetime.timedelta,
        alertmanager_deadman_inhibition_alert_label_filter: dict[str, str],
        forwarder_deadman_interval: datetime.timedelta,
        forwarder_deadman_at_start: bool = True,
        now: datetime.datetime | None = None,
        logger: Logger | None = None
    ):
        if alertmanager_deadman_timeout.total_seconds() <= 0:
            raise ValueError("alertmanager_deadman_timeout must be positive")

        if alertmanager_deadman_timeout.total_seconds() >= 60 * 60 * 24 * 365:
            raise ValueError("alertmanager_deadman_timeout is unreasonably long (1+ years)")
            # note: we allow that for the forwarder_deadman_interval,
            # in case the user does not want those emails at all

        if forwarder_deadman_interval.total_seconds() <= 0:
            raise ValueError("forwarder_deadman_interval must be positive")

        self.forwarder_deadman_interval = forwarder_deadman_interval
        self.forwarder_deadman_at_start = forwarder_deadman_at_start
        self.alertmanager_deadman_timeout = alertmanager_deadman_timeout
        self.alertmanager_deadman_interval = alertmanager_deadman_interval
        self.alertmanager_deadman_inhibition_alert_label_filter = alertmanager_deadman_inhibition_alert_label_filter
        self.last_alertmanager_checkin_timestamp = now or datetime.datetime.now()
        self.alertmanager_deadman_last_sent = None
        self.forwarder_deadman_last_sent = None
        self.logger = logger or Logger("deadman")

    def inhibition_filter_to_string(self) -> str:
        """Return a string representation of the inhibition filter labels."""
        if len(self.alertmanager_deadman_inhibition_alert_label_filter) == 0:
            return "<none>"
        return ",".join(f"{k}={v}" for k, v in self.alertmanager_deadman_inhibition_alert_label_filter.items())

    def does_alert_match_inhibition_label_filter(self, alert_labels: dict[str, str]) -> bool:
        """Check whether the given alert should be considered the inhibition-alert for the alertmanager-deadman-switch."""
        if len(self.alertmanager_deadman_inhibition_alert_label_filter) == 0:
            return False

        for key, value in self.alertmanager_deadman_inhibition_alert_label_filter.items():
            if value == "" and key not in alert_labels:
                return False
            if value != "" and alert_labels.get(key) != value:
                return False

        return True

    def notify_alertmanager_deadman_checkin(self, now: datetime.datetime | None = None) -> None:
        """Notify the deadman switch that alertmanager checked in."""
        now = now or datetime.datetime.now()
        self.logger.debug("Alertmanager checked in, updating last checkin timestamp to %s", now)
        self.last_alertmanager_checkin_timestamp = now

    def notify_mail_sent(self, now: datetime.datetime | None = None) -> None:
        """Notify the deadman switch that the forwarder has sent some email."""
        self.forwarder_deadman_last_sent = now or datetime.datetime.now()

    def is_alertmanager_deadman_expired(self, now: datetime.datetime | None = None) -> bool:
        """Check whether the alertmanager deadman switch has expired."""
        now = now or datetime.datetime.now()
        return (now - self.last_alertmanager_checkin_timestamp) > self.alertmanager_deadman_timeout

    def is_alertmanager_deadman_due(self, now: datetime.datetime | None = None) -> bool:
        """
        Check whether the alertmanager deadman switch is due:
        It is so, only when it is expired and our resend-interval has elapsed since the last email.
        """
        now = now or datetime.datetime.now()
        if not self.is_alertmanager_deadman_expired(now):
            return False

        if self.alertmanager_deadman_last_sent is None:
            return True

        return (now - self.alertmanager_deadman_last_sent) > self.alertmanager_deadman_interval

    def has_sent_startup_deadman_email(self) -> bool:
        """Check whether the forwarder deadman switch email has been sent at startup."""
        return self.forwarder_deadman_last_sent is not None

    def is_forwarder_deadman_due(self, now: datetime.datetime | None = None) -> bool:
        """Check whether the forwarder deadman switch email is due."""
        now = now or datetime.datetime.now()
        if self.forwarder_deadman_last_sent is None:
            return self.forwarder_deadman_at_start
        return (now - self.forwarder_deadman_last_sent) > self.forwarder_deadman_interval

    def get_forwarder_deadman_due_in(self, now: datetime.datetime | None = None) -> datetime.timedelta:
        """Get the time until the forwarder deadman switch email is due."""
        now = now or datetime.datetime.now()
        if self.forwarder_deadman_last_sent is None:
            return datetime.timedelta(seconds=0) if self.forwarder_deadman_at_start else self.forwarder_deadman_interval
        return max(datetime.timedelta(seconds=0), self.forwarder_deadman_interval - (now - self.forwarder_deadman_last_sent))

    def get_alertmanager_deadman_due_in(self, now: datetime.datetime | None = None) -> datetime.timedelta:
        """Get the time until the alertmanager deadman switch email is due."""
        now = now or datetime.datetime.now()
        if not self.is_alertmanager_deadman_expired(now):
            return self.alertmanager_deadman_timeout - (now - self.last_alertmanager_checkin_timestamp)
        if self.alertmanager_deadman_last_sent is None:
            return datetime.timedelta(seconds=0)
        return max(datetime.timedelta(seconds=0), self.alertmanager_deadman_interval - (now - self.alertmanager_deadman_last_sent))

    def notify_forwarder_deadman_sent(self, now: datetime.datetime | None = None) -> None:
        """Notify the deadman switch that the forwarder deadman switch email has been sent."""
        self.forwarder_deadman_last_sent = now or datetime.datetime.now()
    def notify_alertmanager_deadman_sent(self, now: datetime.datetime | None = None) -> None:
        """Notify the deadman switch that the alertmanager deadman switch email has been sent."""
        now = now or datetime.datetime.now()
        self.alertmanager_deadman_last_sent = now
        self.forwarder_deadman_last_sent = now # if we have sent an email, we dont need to brag about being alive still

    def _check_deadman_switches(
        self,
        on_forwarder_deadman_due: Callable[[], None],
        on_alertmanager_deadman_due: Callable[[], None]
    ) -> None:
        """Check both deadman switches and call the appropriate callbacks if they are due/expired."""
        self.logger.debug("Checking deadman switches: forwarder due in %s, alertmanager due in %s",
            self.get_forwarder_deadman_due_in(),
            self.get_alertmanager_deadman_due_in()
        )

        if self.is_alertmanager_deadman_due():
            on_alertmanager_deadman_due()
        if self.is_forwarder_deadman_due():
            on_forwarder_deadman_due()

    def dispatch_scheduler(
        self,
        on_forwarder_deadman_due: Callable[[], None],
        on_alertmanager_deadman_due: Callable[[], None],
        check_interval: datetime.timedelta = datetime.timedelta(seconds=30)
    ) -> BaseScheduler:
        """
        Start off a background scheduler to check the deadman switches periodically.
        Returns immediately the scheduler object, which can be used to stop the scheduler later.
        """
        scheduler = BackgroundScheduler(timezone=datetime.datetime.now().astimezone().tzinfo)

        scheduler.add_job( # type: ignore
            func=lambda: self._check_deadman_switches(on_forwarder_deadman_due, on_alertmanager_deadman_due),
            trigger="interval",
            seconds=check_interval.total_seconds(),
            max_instances=1,
            replace_existing=True,
            id="deadman_switch_check",
            next_run_time=datetime.datetime.now() + datetime.timedelta(seconds=1)
        )
        scheduler.start() # type: ignore

        return scheduler
