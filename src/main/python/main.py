"""Web API for converting Alertmanager webhooks into Microsoft Graph emails."""

import os
from typing import Any
from flask import Flask, request, Response

from http_server import static_bearer_auth
from graph_mail import GraphMailSender
from alertmanager import Notification, Deduplicator
from template import render_mail_body, render_mail_subject
from config import Configuration

flask = Flask(__name__)

CONFIGURATION = Configuration()
MAIL_SENDER = GraphMailSender.default(
    client_id=CONFIGURATION.client_id,
    client_secret=CONFIGURATION.client_secret,
    tenant_id=CONFIGURATION.tenant_id,
    from_address=CONFIGURATION.from_address,
    default_to_address=CONFIGURATION.to_addresses,
    timeout_seconds=CONFIGURATION.http_timeout_seconds,
)
DEDUPLICATOR = Deduplicator()

@flask.get("/health")
def health_check() -> Response:
    """Health check endpoint."""
    return Response("Up", status=200, mimetype="text/plain")


@flask.post("/alert")
@static_bearer_auth(token=os.getenv("AUTH_TOKEN", ""))
def on_webhook() -> Response:
    """Handle incoming Alertmanager webhook and send email via Microsoft Graph API."""

    data: dict[str, Any] | None = request.get_json(silent=True)
    if not isinstance(data, dict):
        return Response("Invalid JSON body", status=400, mimetype="text/plain")

    if data.get("version") != "4":
        return Response("Unsupported Alertmanager version", status=400, mimetype="text/plain")

    notification = Notification.parse(data)

    if DEDUPLICATOR.is_present(notification.group_key):
        return Response("Duplicate notification", status=200, mimetype="text/plain")

    for i in range(len(notification.alerts)):
        MAIL_SENDER.send(
            subject=render_mail_subject(notification, alert_index=i),
            body=render_mail_body(notification, alert_index=i)
            # to=<use default>
        )

    # partial failure of sending will lead to duplicate emails when appending only here,
    # but we accept that for simplicity
    DEDUPLICATOR.add(notification.group_key)

    return Response(status=200)


if __name__ == "__main__":
    flask.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
    # run in prod configuration: gunicorn -k gthread -b 0.0.0.0:8000 main:flask
