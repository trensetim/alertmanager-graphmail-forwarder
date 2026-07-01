"""Web API for converting Alertmanager webhooks into Microsoft Graph emails."""

import sys
from typing import Any
from flask import Flask, request, Response

from http_server import static_bearer_auth
from graph_mail import GraphMailSender
from alertmanager import Notification, Deduplicator
from deadman import Deadman
from template import TemplateRenderer
from config import Configuration

flask = Flask(__name__)
LOGGER = flask.logger.getChild("main")

config: Configuration
try:
    config = Configuration()
    LOGGER.setLevel(config.log_level)
except ValueError as e:
    LOGGER.error("Configuration error: %s", e)
    sys.exit(1)

RENDERER = TemplateRenderer(subject_tags=config.subject_tags)
MAIL_SENDER = GraphMailSender.default(
    client_id=config.client_id,
    client_secret=config.client_secret,
    tenant_id=config.tenant_id,
    from_address=config.from_address,
    default_to_address=config.to_addresses,
    timeout_seconds=config.http_timeout_seconds,
)
DEDUPLICATOR = Deduplicator()
DEADMAN = Deadman(
    config.deadman_alertmanager_timeout,
    config.deadman_alertmanager_interval,
    config.deadman_forwarder_interval,
    config.deadman_forwarder_at_start,
    logger=LOGGER.getChild("deadman")
)

@flask.get("/health")
def health_check() -> Response:
    """Health check endpoint."""
    return Response("Up", status=200, mimetype="text/plain")

@flask.get("/preview/example/body")
def preview_example_body() -> Response:
    """Preview the email body for a static sample Alertmanager webhook payload."""
    data: dict[str, Any] = {
        "version": "4",
        "groupKey": "example_group",
        "status": "firing",
        "receiver": "alertmanager-graphmail-forwarder",
        "externalURL": "https://example.com",
        "alerts": [{
            "status": "firing",
            "labels": {
                "alertname": "ExampleAlert",
                "label-foo": "bar"
            },
            "annotations": {
                "summary": "This is an example alert",
                "annotation-foo": "bar",
                "annotation-123": "456",
            },
            "startsAt": "2024-01-01T00:00:00Z",
            "endsAt": "2024-01-01T01:00:00Z",
            "generatorURL": "https://example.com/alert",
            "fingerprint": "example_fingerprint"
        }]
    }
    notification = Notification.parse(data)
    body = RENDERER.render_mail_body(notification, alert_index=0)
    return Response(body, status=200, mimetype="text/html")

@flask.get("/preview/example/forwarder_deadman")
def preview_example_forwarder_deadman() -> Response:
    """Preview the forwarder deadman email body for a static sample Alertmanager webhook payload."""
    body = RENDERER.render_forwarder_deadman_body()
    return Response(body, status=200, mimetype="text/html")

@flask.get("/preview/example/alertmanager_deadman")
def preview_example_alertmanager_deadman() -> Response:
    """Preview the alertmanager deadman email body for a static sample Alertmanager webhook payload."""
    body = RENDERER.render_alertmanager_deadman_body()
    return Response(body, status=200, mimetype="text/html")

@flask.post("/alert")
@static_bearer_auth(
    token=config.server.auth_token or "",
    allow_anonymous=config.server.is_auth_enabled() is False
)
def on_webhook() -> Response:
    """Handle incoming Alertmanager webhook and send email via Microsoft Graph API."""

    data: dict[str, Any] | None = request.get_json(silent=True)
    if not isinstance(data, dict):
        return Response("Invalid JSON body", status=400, mimetype="text/plain")

    if data.get("version") != "4":
        return Response("Unsupported Alertmanager version", status=400, mimetype="text/plain")

    notification = Notification.parse(data)

    # we only count the checkin, if all checks pass (ie. no malformed input),
    # but before the deduplication, since we respect ANY signs of life
    DEADMAN.notify_alertmanager_deadman_checkin()

    if DEDUPLICATOR.is_present(notification.group_key):
        LOGGER.warning("Duplicate notification received: %s", notification.group_key)
        return Response("Duplicate notification", status=200, mimetype="text/plain")

    for i in range(len(notification.alerts)):
        MAIL_SENDER.send(
            subject=RENDERER.render_mail_subject(notification, alert_index=i),
            body=RENDERER.render_mail_body(notification, alert_index=i)
            # to=<use default>
        )

    # partial failure of sending will lead to duplicate emails when appending only here,
    # but we accept that for simplicity
    DEDUPLICATOR.add(notification.group_key)

    LOGGER.info("Notification processed: %d alerts sent", len(notification.alerts))
    LOGGER.debug("%s", notification)
    return Response(status=200)

def on_forwarder_deadman_due() -> None:
    """Callback for when the forwarder deadman switch is due."""
    LOGGER.info("Forwarder deadman switch is due, sending email...")
    MAIL_SENDER.send(
        subject=RENDERER.render_forwarder_deadman_subject(),
        body=RENDERER.render_forwarder_deadman_body()
    )
    DEADMAN.notify_forwarder_deadman_sent()

def on_alertmanager_deadman_due() -> None:
    """Callback for when the alertmanager deadman switch is due."""
    LOGGER.info("Alertmanager deadman switch is due, sending email...")
    MAIL_SENDER.send(
        subject=RENDERER.render_alertmanager_deadman_subject(),
        body=RENDERER.render_alertmanager_deadman_body()
    )
    DEADMAN.notify_alertmanager_deadman_sent()

if __name__ == "__main__":
    if not config.deadman_disabled:
        LOGGER.info("Forwarder deadman switch is enabled, installing scheduler at interval %s", config.deadman_interval)
        DEADMAN.dispatch_scheduler(on_forwarder_deadman_due, on_alertmanager_deadman_due, config.deadman_interval)
    else:
        LOGGER.info("Forwarder deadman switch is disabled")

    flask.run(
        host=config.server.listen_address,
        port=config.server.listen_port,
        ssl_context=config.server.tls.load_ssl_context() if config.server.tls else None,
        debug=True,
        use_reloader=False # https://stackoverflow.com/a/15491587
    ) # run in prod configuration: gunicorn -k gthread -b 0.0.0.0:8000 main:flask
