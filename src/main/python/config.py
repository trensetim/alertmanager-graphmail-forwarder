"""Configuration management for the application."""

from dataclasses import dataclass
import os
import re

ENV_VAR_CLIENT_ID = "CLIENT_ID"
ENV_VAR_CLIENT_SECRET = "CLIENT_SECRET"
ENV_VAR_TENANT_ID = "TENANT_ID"
ENV_VAR_FROM_ADDRESS = "FROM"
ENV_VAR_TO_ADDRESSES = "TO"
ENV_VAR_HTTP_TIMEOUT_SECONDS = "HTTP_TIMEOUT_SECONDS"
ENV_VAR_LISTEN_ADDRESS = "LISTEN_ADDRESS"
ENV_VAR_LISTEN_PORT = "LISTEN_PORT"
ENV_VAR_AUTH_TOKEN = "AUTH_TOKEN"

BASE_EMAIL_LIST_REGEX = r'(([A-Za-z0-9\-\._~\+]+@[A-Za-z0-9\-\._~\+]+\.[A-Za-z]{2,}),?)+'

@dataclass
class Configuration:
    """
    Runtime configuration for the application.
    Parsed from all config sources (in this app: only environment variables).
    """

    client_id: str
    """OAuth2 Client ID for Microsoft Graph API authentication."""
    client_secret: str
    """OAuth2 Client Secret for Microsoft Graph API authentication."""
    tenant_id: str
    """Azure AD Tenant ID for Microsoft Graph API authentication."""
    from_address: str
    """Email address used as the sender in outgoing emails."""
    to_addresses: list[str]
    """Recipient email addresses for outgoing emails."""
    http_timeout_seconds: float
    """HTTP timeout for requests to Microsoft Graph API."""
    listen_address: str
    """HTTP server listen address for incoming requests."""
    listen_port: int
    """HTTP server listen port for incoming requests."""
    auth_token: str | None
    """Bearer token for static authentication."""
    no_auth: bool
    """Whether to disable authentication (for testing purposes)."""

    def __init__(self):
        client_id: str = os.getenv(ENV_VAR_CLIENT_ID, "")
        client_secret: str = os.getenv(ENV_VAR_CLIENT_SECRET, "")
        tenant_id: str = os.getenv(ENV_VAR_TENANT_ID, "")
        from_address: str = os.getenv(ENV_VAR_FROM_ADDRESS, "")
        to_addresses_raw: str = os.getenv(ENV_VAR_TO_ADDRESSES, "")
        http_timeout_seconds_str: str = os.getenv(ENV_VAR_HTTP_TIMEOUT_SECONDS, "10.0")
        listen_address: str = os.getenv(ENV_VAR_LISTEN_ADDRESS, "0.0.0.0")
        listen_port_str: str = os.getenv(ENV_VAR_LISTEN_PORT, "8080")
        auth_token: str = os.getenv(ENV_VAR_AUTH_TOKEN, "")

        if client_id == "":
            raise ValueError(f"{ENV_VAR_CLIENT_ID} not configured")
        if client_secret == "":
            raise ValueError(f"{ENV_VAR_CLIENT_SECRET} not configured")
        if tenant_id == "":
            raise ValueError(f"{ENV_VAR_TENANT_ID} not configured")
        if (
            from_address == ""
            or not re.fullmatch(BASE_EMAIL_LIST_REGEX, from_address)
            or ',' in from_address
        ):
            raise ValueError(f"{ENV_VAR_FROM_ADDRESS} invalid")
        if (
            to_addresses_raw == ""
            or not re.fullmatch(BASE_EMAIL_LIST_REGEX, to_addresses_raw)
        ):
            raise ValueError(f"{ENV_VAR_TO_ADDRESSES} invalid")
        if (
            http_timeout_seconds_str == ""
            or not re.fullmatch(r'^[0-9]+(\.[0-9]+)?$', http_timeout_seconds_str)
            or float(http_timeout_seconds_str) <= 0.0
            # 10m exceeds reasonable TCP timeout thus user likely misinterpreted it as millis
            or float(http_timeout_seconds_str) > 600.0
        ):
            raise ValueError(f"{ENV_VAR_HTTP_TIMEOUT_SECONDS} invalid")
        if listen_address == "":
            raise ValueError(f"{ENV_VAR_LISTEN_ADDRESS} not configured")
        if (
            listen_port_str == ""
            or not re.fullmatch(r'^[0-9]+$', listen_port_str)
            or int(listen_port_str) < 1
            or int(listen_port_str) >= 65535
        ):
            raise ValueError(f"{ENV_VAR_LISTEN_PORT} invalid")
        if (
            auth_token == ""
            or not re.fullmatch(r'^[A-Za-z0-9\-\._~\+/]+=*$', auth_token)
        ):
            raise ValueError(f"{ENV_VAR_AUTH_TOKEN} invalid")

        auth_token = _coalesce_file(auth_token, ENV_VAR_AUTH_TOKEN)
        client_id = _coalesce_file(client_id, ENV_VAR_CLIENT_ID)
        client_secret = _coalesce_file(client_secret, ENV_VAR_CLIENT_SECRET)
        tenant_id = _coalesce_file(tenant_id, ENV_VAR_TENANT_ID)

        self.client_id = client_id
        self.client_secret = client_secret
        self.tenant_id = tenant_id
        self.from_address = from_address
        self.to_addresses = to_addresses_raw.split(',')
        self.http_timeout_seconds = float(http_timeout_seconds_str)
        self.listen_address = listen_address
        self.listen_port = int(listen_port_str)
        self.no_auth = auth_token == "DISABLED"
        self.auth_token = auth_token if not self.no_auth else None

def _coalesce_file(secret: str, hint: str) -> str:
    """
    If the given secret starts with a '/',
    treat it as a file path and read the secret from there.
    Otherwise, return the secret as-is.
    """
    if secret.startswith("/"):
        try:
            with open(secret, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception as e:
            raise ValueError(f"Failed to read secret from file ({hint})") from e
    return secret
