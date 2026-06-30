"""Configuration management for the application."""

from collections.abc import Callable
import datetime
import isodate
import os
import re
from dataclasses import dataclass
import ssl
import logging
import csv

ENV_VAR_CLIENT_ID = "CLIENT_ID"
ENV_VAR_CLIENT_SECRET = "CLIENT_SECRET"
ENV_VAR_TENANT_ID = "TENANT_ID"
ENV_VAR_FROM_ADDRESS = "FROM"
ENV_VAR_TO_ADDRESSES = "TO"
ENV_VAR_HTTP_TIMEOUT_SECONDS = "HTTP_TIMEOUT_SECONDS"
ENV_VAR_LISTEN_ADDRESS = "LISTEN_ADDRESS"
ENV_VAR_LISTEN_PORT = "LISTEN_PORT"
ENV_VAR_AUTH_TOKEN = "AUTH_TOKEN"
ENV_VAR_TLS_CERT_PATH = "TLS_CERT_PATH"
ENV_VAR_TLS_KEY_PATH = "TLS_KEY_PATH"
ENV_VAR_LOG_LEVEL = "LOG_LEVEL"
ENV_VAR_PROMETHEUS_NAMING_STRICT = "PROMETHEUS_NAMING_STRICT"
ENV_VAR_SUBJECT_TAGS = "SUBJECT_TAGS"
ENV_VAR_DEADMAN_DISABLED = "DEADMAN_DISABLED"
ENV_VAR_DEADMAN_INTERVAL = "DEADMAN_INTERVAL"
ENV_VAR_DEADMAN_FORWARDER_AT_START = "DEADMAN_FORWARDER_AT_START"
ENV_VAR_DEADMAN_FORWARDER_INTERVAL = "DEADMAN_FORWARDER_INTERVAL"
ENV_VAR_DEADMAN_ALERTMANAGER_TIMEOUT = "DEADMAN_ALERTMANAGER_TIMEOUT"
ENV_VAR_DEADMAN_ALERTMANAGER_INTERVAL = "DEADMAN_ALERTMANAGER_INTERVAL"

BASE_EMAIL_LIST_REGEX = r'(([A-Za-z0-9\-\._~\+]+@[A-Za-z0-9\-\._~\+]+\.[A-Za-z]{2,}),?)+'

@dataclass
class TlsConfiguration:
    """
    TLS configuration for the HTTP server.
    """

    cert_path: str
    """Filesystem path to a TLS certificate file."""
    key_path: str
    """Filesystem path to a TLS private key file."""

    def __init__(self, cert_path: str, key_path: str):
        self.cert_path = cert_path
        self.key_path = key_path

    def load_ssl_context(self) -> ssl.SSLContext:
        """
        Loads an SSL context from the TLS configuration.
        """
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ssl_context.load_cert_chain(
            certfile=self.cert_path,
            keyfile=self.key_path,
        )
        return ssl_context

@dataclass
class HttpServerConfiguration:
    """
    HTTP server configuration.
    """

    listen_address: str
    """HTTP server listen address for incoming requests."""
    listen_port: int
    """HTTP server listen port for incoming requests."""
    auth_token: str | None
    """Bearer token for static authentication."""
    tls: TlsConfiguration | None
    """TLS configuration for the HTTP server."""

    def __init__(
        self,
        listen_address: str,
        listen_port: int,
        auth_token: str | None = None,
        tls: TlsConfiguration | None = None,
    ):
        self.listen_address = listen_address
        self.listen_port = listen_port
        self.auth_token = auth_token
        self.tls = tls

    def is_auth_enabled(self) -> bool:
        """Whether authentication is enabled."""
        return self.auth_token is not None

class PrometheusNameParser:
    """
    Contains logic to parse Prometheus-style metric names, label names and annotation names.

    Validity rules are outlined in
    https://prometheus.io/docs/concepts/data_model/#metric-names-and-labels

    Note:
        - This implementation adheres to Prometheus v3 rules, which allow UTF-8 in names.
        - This implementation allows special characters, because the Prometheus naming convention
            only states a SHOULD-regex. If you want hard enforcement, use the ..._stict methods.

    """

    strict_mode: bool = False
    """Whether to enforce strict Prometheus v2 naming conventions."""

    _METRIC_NAME_PATTERN_STRICT = r'^[a-zA-Z_:][a-zA-Z0-9_:]*$'
    _LABEL_NAME_PATTERN_STRICT = r'^[a-zA-Z_][a-zA-Z0-9_]*$'
    _RELAXED_PATTERN = r'^[^"\']+$'

    def __init__(self, strict_mode: bool = False) -> None:
        self.strict_mode = strict_mode

    def _get_metric_pattern(self) -> str:
        return (
            self._METRIC_NAME_PATTERN_STRICT
                if self.strict_mode
                else self._RELAXED_PATTERN
        )
    def _get_label_pattern(self) -> str:
        return (
            self._LABEL_NAME_PATTERN_STRICT
                if self.strict_mode
                else self._RELAXED_PATTERN
        )

    def parse_metric_name(self, name: str) -> str:
        """
        Validates a Prometheus-style metric name according to the SHOULD-regex.
        Throws, if invalid.
        """
        return self._parse_name(name, self._get_metric_pattern())

    def parse_label_name(self, name: str) -> str:
        """
        Validates a Prometheus-style label/annotation name according to the SHOULD-regex.
        Throws, if invalid.
        """
        return self._parse_name(name, self._get_label_pattern())

    def _parse_name(self, name: str, pattern: str) -> str:
        match = re.fullmatch(pattern, name)
        if match is None:
            raise ValueError(f"Invalid Prometheus-style name: {name}")
        return match.group(0)

    def parse_labels_csv(self, names: str) -> list[str]:
        """
        Parses a comma-separated list of Prometheus-style names.
        The names must be quoted with (") or (') if they contain special characters.
        The backslash (\\\\) can be used as an escape character within quoted names.
        Throws, if any name is invalid.

        Note: This method uses the relaxed name validation of Prometheus v3.

        Args:
            names (str): eg. "a,b,'c',\"d_ with sp€cia\\\\\" ch4rs\""

        Returns:
            list[str]: all parsed names
        """
        return self._parse_labels_csv(names, self.parse_label_name)

    def _parse_labels_csv(self, names: str, name_parser_func: Callable[[str], str]) -> list[str]:
        reader = csv.reader([names], escapechar='\\', delimiter=',', skipinitialspace=True)
        line = next(reader)
        return [name_parser_func(name) for name in line if name.strip() != ""]

@dataclass
# pylint: disable=R0902 # too many instance properties -> dataclass
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
    """HTTP timeout in seconds for Microsoft Graph API requests."""
    server: HttpServerConfiguration
    """HTTP server configuration."""
    subject_tags: list[str]
    """Labels and/or Annotations to prepend to email subjects, for easier identification."""
    log_level: int = logging.INFO
    """Logging level for the application."""
    prometheus_naming_strict = False
    """Whether to enforce compatibility (pre-v3) Prometheus naming conventions."""

    deadman_disabled: bool = False
    """Whether to disable the deadman switch functionality."""
    deadman_interval: datetime.timedelta = datetime.timedelta(seconds=30)
    """The interval at which to check the deadman switches."""
    forwarder_deadman_at_start: bool = False
    """Whether to send a deadman-switch email immediately at startup."""
    alertmanager_deadman_timeout: datetime.timedelta = datetime.timedelta(hours=24)
    """How long to wait for any Alertmanager webhook before considering the deadman switch expired."""
    alertmanager_deadman_interval: datetime.timedelta = datetime.timedelta(hours=24)
    """How long to wait between sending consecutive alertmanager deadman emails (if alertmanager is still down)."""
    forwarder_deadman_interval: datetime.timedelta = datetime.timedelta(hours=24)
    """The interval at which to send out deadman-switch emails."""

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
        tls_cert_path: str | None = os.getenv(ENV_VAR_TLS_CERT_PATH)
        tls_key_path: str | None = os.getenv(ENV_VAR_TLS_KEY_PATH)
        log_level: str = os.getenv(ENV_VAR_LOG_LEVEL, "INFO").upper()
        prometheus_naming_strict: bool = (
            os.getenv(ENV_VAR_PROMETHEUS_NAMING_STRICT, "").lower() == "true"
        )
        subject_tags_raw: str = os.getenv(ENV_VAR_SUBJECT_TAGS, "")

        deadman_disabled = bool(os.getenv(ENV_VAR_DEADMAN_DISABLED, "").lower() == "true")
        deadman_interval_raw: str = os.getenv(ENV_VAR_DEADMAN_INTERVAL, "PT30S")
        deadman_interval: datetime.timedelta = isodate.parse_duration(deadman_interval_raw) # type: ignore
        forwarder_deadman_at_start = bool(os.getenv(ENV_VAR_DEADMAN_FORWARDER_AT_START, "false").lower() == "true")
        forwarder_deadman_interval_raw: str = os.getenv(ENV_VAR_DEADMAN_FORWARDER_INTERVAL, "PT24H")
        forwarder_deadman_interval: datetime.timedelta = isodate.parse_duration(forwarder_deadman_interval_raw) # type: ignore
        alertmanager_deadman_timeout_raw: str = os.getenv(ENV_VAR_DEADMAN_ALERTMANAGER_TIMEOUT, "PT24H")
        alertmanager_deadman_timeout: datetime.timedelta = isodate.parse_duration(alertmanager_deadman_timeout_raw) # type: ignore
        alertmanager_deadman_interval_raw: str = os.getenv(ENV_VAR_DEADMAN_ALERTMANAGER_INTERVAL, "PT24H")
        alertmanager_deadman_interval: datetime.timedelta = isodate.parse_duration(alertmanager_deadman_interval_raw) # type: ignore

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
        if (tls_cert_path is None) != (tls_key_path is None):
            raise ValueError("Both TLS_CERT_PATH and TLS_KEY_PATH must be set to enable TLS")
        tls_enabled = tls_cert_path is not None and tls_key_path is not None
        if (tls_enabled and (
            not os.access(tls_cert_path or "", os.R_OK)
            or not os.access(tls_key_path or "", os.R_OK)
        )):
            raise ValueError("TLS certificate or key file not readable")
        if log_level not in logging.getLevelNamesMapping():
            raise ValueError(f"{ENV_VAR_LOG_LEVEL} invalid")

        if isinstance(forwarder_deadman_interval, isodate.Duration):
            forwarder_deadman_interval = forwarder_deadman_interval.totimedelta(start = datetime.datetime.now()) # type: ignore
        if isinstance(alertmanager_deadman_interval, isodate.Duration):
            alertmanager_deadman_interval = alertmanager_deadman_interval.totimedelta(start = datetime.datetime.now()) # type: ignore
        # for deadman_interval and alertmanager_deadman_timeout, we assert that they are
        # not a Duration, because we don't want to allow months/years there, only seconds/minutes/hours/days

        if deadman_interval <= datetime.timedelta(seconds=0): # type: ignore
            raise ValueError(f"{ENV_VAR_DEADMAN_INTERVAL} must be positive")
        if forwarder_deadman_interval <= datetime.timedelta(seconds=0): # type: ignore
            raise ValueError(f"{ENV_VAR_DEADMAN_FORWARDER_INTERVAL} must be positive")
        if alertmanager_deadman_timeout <= datetime.timedelta(seconds=0): # type: ignore
            raise ValueError(f"{ENV_VAR_DEADMAN_ALERTMANAGER_TIMEOUT} must be positive")
        if alertmanager_deadman_interval <= datetime.timedelta(seconds=0): # type: ignore
            raise ValueError(f"{ENV_VAR_DEADMAN_ALERTMANAGER_INTERVAL} must be positive")
        if alertmanager_deadman_timeout >= datetime.timedelta(days=365): # type: ignore
            raise ValueError(f"{ENV_VAR_DEADMAN_ALERTMANAGER_TIMEOUT} is unreasonably long (1+ years)")

        auth_token = _coalesce_file(auth_token, ENV_VAR_AUTH_TOKEN)
        client_id = _coalesce_file(client_id, ENV_VAR_CLIENT_ID)
        client_secret = _coalesce_file(client_secret, ENV_VAR_CLIENT_SECRET)
        tenant_id = _coalesce_file(tenant_id, ENV_VAR_TENANT_ID)

        name_parser = PrometheusNameParser(prometheus_naming_strict)

        self.client_id = client_id
        self.client_secret = client_secret
        self.tenant_id = tenant_id
        self.from_address = from_address
        self.to_addresses = to_addresses_raw.split(',')
        self.http_timeout_seconds = float(http_timeout_seconds_str)
        self.log_level = logging.getLevelNamesMapping()[log_level]
        self.prometheus_naming_strict = prometheus_naming_strict
        self.subject_tags = name_parser.parse_labels_csv(subject_tags_raw)
        self.server = HttpServerConfiguration(
            listen_address=listen_address,
            listen_port=int(listen_port_str),
            auth_token=(auth_token if auth_token != "DISABLED" else None),
            tls=(
                TlsConfiguration(
                    cert_path=tls_cert_path or "",
                    key_path=tls_key_path or ""
                )
                if tls_enabled
                else None
            ),
        )

        self.deadman_disabled = deadman_disabled
        self.deadman_interval = deadman_interval
        self.forwarder_deadman_at_start = forwarder_deadman_at_start
        self.forwarder_deadman_interval = forwarder_deadman_interval
        self.alertmanager_deadman_timeout = alertmanager_deadman_timeout
        self.alertmanager_deadman_interval = alertmanager_deadman_interval

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
