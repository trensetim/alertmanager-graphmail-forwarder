"""Module for rendering a notification into an HTML email body."""

from typing import Any
from jinja2 import Environment, PackageLoader, select_autoescape

from alertmanager import Notification

class TemplateRenderer:
    """
    Class for rendering mail notification templates.
    The template language is Jinja2.
    """

    subject_tags: list[str] = []
    """Labels and/or Annotations to prepend to email subjects, for easier identification."""

    def __init__(self, subject_tags: list[str] | None = None):
        self.subject_tags = subject_tags if subject_tags is not None else []
        self._jinja_env = Environment(
            loader=PackageLoader(__name__, "templates"),
            autoescape=select_autoescape()
        )

    def _render_subject_tags(self, notification: Notification, alert_index: int) -> dict[str, str]:
        if alert_index < 0 or alert_index >= len(notification.alerts):
            raise IndexError("alert_index out of range")
        alert = notification.alerts[alert_index]

        tags: dict[str, str] = {}
        for tag in self.subject_tags:
            value = alert.labels.get(tag) or alert.annotations.get(tag)
            if value is not None:
                tags[tag] = value
        return tags

    def _render_properties(self, notification: Notification, alert_index: int) -> dict[str, Any]:
        if alert_index < 0 or alert_index >= len(notification.alerts):
            raise IndexError("alert_index out of range")
        alert = notification.alerts[alert_index]

        labels = {
            key: value
            for key, value in alert.labels.items()
            if key != "alertname"
        }
        annotations = {
            key: value
            for key, value in alert.annotations.items()
            if key not in ("summary", "description")
        }
        subject_tag_values = self._render_subject_tags(notification, alert_index)

        return {
            "notification": notification,
            "alert_index": alert_index,
            "status": alert.status.value.upper(),
            "external_url": notification.external_url,
            "alertname": alert.labels.get("alertname", "[no alert name]"),
            "summary": alert.annotations.get("summary", "[no summary]"),
            "description": alert.annotations.get("description", "[no description]"),
            "starts_at": alert.starts_at.isoformat(),
            "ends_at":
                alert.ends_at.isoformat()
                if alert.ends_at is not None and alert.ends_at.timestamp() > 1
                else "ongoing",
            "fingerprint": alert.fingerprint,
            "labels": labels,
            "annotations": annotations,
            "subject_tags": self.subject_tags,
            "subject_tag_values": subject_tag_values,
        }

    def render_mail_subject(self, notification: Notification, alert_index: int) -> str:
        """Render the email subject for a given notification."""
        properties = self._render_properties(notification, alert_index)
        template = self._jinja_env.get_template("subject.txt.jinja")
        return template.render(**properties)

    def render_mail_body(self, notification: Notification, alert_index: int) -> str:
        """Render the email body for a given notification."""
        properties = self._render_properties(notification, alert_index)
        template = self._jinja_env.get_template("body.html.jinja")
        return template.render(**properties)
