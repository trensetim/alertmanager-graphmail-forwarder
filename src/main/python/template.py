"""Module for rendering a notification into an HTML email body."""

from string import Template

from alertmanager import Notification

_PAGE_SRC = Template("""
<html>
<body>
    <h2>$status: $alert_name</h2>

    <table>
    <tbody>
    <tr>
        <td>Summary</td>
        <td>$summary</td>
    </tr>
    <tr>
        <td>Description</td>
        <td>$description</td>
    </tr>
    <tr>
        <td>Starts At</td>
        <td>$starts_at</td>
    </tr>
    <tr>
        <td>Ends At</td>
        <td>$ends_at</td>
    </tr>
    <tr>
        <td>Fingerprint</td>
        <td>$fingerprint</td>
    </tr>
    <tr>
        <td>Labels</td>
        <td>
            <ul>
            $labels
            </ul>
        </td>
    </tr>
    <tr>
        <td>Annotations</td>
        <td>
            <ul>
            $annotations
            </ul>
        </td>
    </tr>
    </tbody>
    </table>

    <hr/>
    <a href="$external_url">View in Alertmanager</a>
</body>
</html>
""")

def render_mail_subject(notification: Notification, alert_index: int) -> str:
    """Render the email subject for a given notification."""
    alert = notification.alerts[alert_index]
    alertname = alert.labels.get("alertname", "[no alert name]")
    return f"[alert {notification.status.value.upper()}] {alertname}"

def render_mail_body(notification: Notification, alert_index: int) -> str:
    """Render the email body for a given notification."""

    if alert_index < 0 or alert_index >= len(notification.alerts):
        raise IndexError("alert_index out of range")

    alert = notification.alerts[alert_index]

    labels = "\n".join(
        f"<li><b>{key}</b>={value}</li>"
        for key, value in alert.labels.items()
        if key != "alertname"
    )
    annotations = "\n".join(
        f"<li><b>{key}</b>={value}</li>"
        for key, value in alert.annotations.items()
        if key not in ("summary", "description")
    )

    rendered = _PAGE_SRC.substitute(
        status=alert.status.value.upper(),
        external_url=notification.external_url,
        alert_name=alert.labels.get("alertname", "[no alert name]"),
        summary=alert.annotations.get("summary", "[no summary]"),
        description=alert.annotations.get("description", "[no description]"),
        starts_at=alert.starts_at.isoformat(),
        ends_at=alert.ends_at.isoformat() if alert.ends_at else "[no end time]",
        fingerprint=alert.fingerprint,
        labels=labels,
        annotations=annotations
    )

    return rendered
