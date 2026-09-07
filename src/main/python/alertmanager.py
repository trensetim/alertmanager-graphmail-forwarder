"""Data Structures for Alertmanager webhook payloads."""

import enum
from datetime import datetime
from dataclasses import dataclass
from typing import Any

class Status(enum.Enum):
    """Notification Status"""
    FIRING = "firing"
    RESOLVED = "resolved"

@dataclass
class Alert:
    """An individual alert."""

    status: Status
    """status of the alert (firing/resolved)"""

    labels: dict[str, str]
    """labels associated with the alert"""

    annotations: dict[str, str]
    """annotations associated with the alert"""

    starts_at: datetime
    """when the alert started"""

    ends_at: datetime | None
    """when the alert ended"""

    generator_url: str
    """identifies the entity that caused the alert"""

    fingerprint: str
    """fingerprint to identify the alert"""

    alertname: str
    """Taken from labels (optional, default "[no alert name]")"""
    summary: str
    """Taken from annotations (optional, default "[no summary]")"""
    description: str
    """Taken from annotations (optional, default "[no description]")"""

    def __init__(self,
                 status: Status,
                 labels: dict[str, str],
                 annotations: dict[str, str],
                 starts_at: datetime,
                 ends_at: datetime | None,
                 generator_url: str,
                 fingerprint: str):
        self.status = status
        self.labels = labels
        self.annotations = annotations
        self.starts_at = starts_at
        self.ends_at = ends_at
        self.generator_url = generator_url
        self.fingerprint = fingerprint

        self.alertname = labels.get("alertname", "[no alert name]")
        self.summary = annotations.get("summary", "[no summary]")
        self.description = annotations.get("description", "[no description]")

@dataclass
# pylint: disable=R0902 # too few public methods -> dataclass
class Notification:
    """https://prometheus.io/docs/alerting/latest/configuration/#webhook_config"""

    version: int
    """4"""

    group_key: str
    """key identifying the group of alerts"""

    external_url: str
    """backlink to the Alertmanager"""

    status: Status
    """overall status of the notification"""

    receiver: str
    """name of the receiver"""

    group_labels: dict[str, str]
    """labels common to all alerts in this group"""

    common_labels: dict[str, str]
    """labels common to all alerts in this notification"""

    common_annotations: dict[str, str]
    """annotations common to all alerts in this notification"""

    alerts: list[Alert]
    """list of alerts contained in this notification"""

    # pylint: disable=R0913 R0917 # too many arguments -> dataclass
    def __init__(self,
                 version: int,
                 group_key: str,
                 status: Status,
                 receiver: str,
                 group_labels: dict[str, str],
                 common_labels: dict[str, str],
                 common_annotations: dict[str, str],
                 external_url: str,
                 alerts: list[Alert]):
        self.version = version
        self.group_key = group_key
        self.status = status
        self.receiver = receiver
        self.group_labels = group_labels
        self.common_labels = common_labels
        self.common_annotations = common_annotations
        self.external_url = external_url
        self.alerts = alerts

    @staticmethod
    def parse(data: dict[str, Any]) -> "Notification":
        """Create Notification from dictionary."""

        if data["version"] != "4":
            raise ValueError("Unsupported Alertmanager version")

        alerts = [
            Alert(
                status=Status(alert_data["status"]),
                labels=alert_data["labels"],
                annotations=alert_data["annotations"],
                starts_at=datetime.fromisoformat(alert_data["startsAt"].replace("Z", "+00:00")),
                ends_at=datetime.fromisoformat(alert_data["endsAt"].replace("Z", "+00:00")),
                generator_url=alert_data["generatorURL"],
                fingerprint=alert_data["fingerprint"]
            )
            for alert_data in data.get("alerts", [])
        ]

        return Notification(
            version=int(data["version"]),
            group_key=data["groupKey"],
            status=Status(data["status"]),
            receiver=data["receiver"],
            group_labels=data.get("groupLabels", {}),
            common_labels=data.get("commonLabels", {}),
            common_annotations=data.get("commonAnnotations", {}),
            external_url=data["externalURL"],
            alerts=alerts
        )
