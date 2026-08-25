"""Module for sending mails via the Microsoft Graph API."""

from datetime import datetime, timedelta
from typing import Any, cast
import requests

class _Authenticator:
    """
    Handles an OAuth2 client credentials grant flow with Microsoft Graph API.
    Gets an OAuth2 access token and caches it.
    """

    _cached_access_token: str | None = None
    _cache_expires_at: datetime | None = None

    _oauth_client_id: str
    _oauth_client_secret: str
    _oauth_scope: str
    _oauth_token_url: str
    _oauth_http_timeout_seconds: float = 10.0

    def __init__(self,
                 client_id: str,
                 client_secret: str,
                 tenant_id: str,
                 scope: str = 'https://graph.microsoft.com/.default',
                 http_timeout_seconds: float = 10.0
    ):
        self._oauth_client_id = client_id
        self._oauth_client_secret = client_secret
        self._oauth_token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
        self._oauth_scope = scope
        self._oauth_http_timeout_seconds = http_timeout_seconds

    def now(self) -> datetime:
        """Get current datetime."""
        return datetime.now()

    def get_access_token(self) -> str:
        """Get a valid access token, refreshing it if necessary."""

        if (self._cached_access_token is not None
            and self._cache_expires_at is not None
            and self.now() < self._cache_expires_at
        ):
            return self._cached_access_token

        data = {
            'client_id': self._oauth_client_id,
            'scope': self._oauth_scope,
            'client_secret': self._oauth_client_secret,
            'grant_type': 'client_credentials'
        }
        resp = requests.post(
            self._oauth_token_url,
            data=data,
            timeout=self._oauth_http_timeout_seconds)
        resp.raise_for_status()
        json_resp = resp.json()

        expires_in_seconds = int(json_resp.get('expires_in', 3600))

        if expires_in_seconds <= 0:
            raise RuntimeError("Invalid expires_in value from Microsoft Graph API")

        if (
            json_resp['access_token'] is None
            or not isinstance(json_resp['access_token'], str)
            or json_resp['access_token'] == ''
        ):
            raise RuntimeError("Failed to obtain access token from Microsoft Graph API")

        self._cached_access_token = json_resp.get('access_token', '')
        self._cache_expires_at = (
            self.now() +
            timedelta(seconds=expires_in_seconds - self._oauth_http_timeout_seconds*2)
        )
        return cast(str, self._cached_access_token)

class GraphMailSender:
    """Sends mails via the Microsoft Graph API."""
    _authenticator: _Authenticator
    _timeout_seconds: float = 10.0
    _from_address: str
    _default_to_address: list[str] = []
    """default recipients if not specified in send()"""

    def __init__(self,
                 authenticator: _Authenticator,
                 from_address: str,
                 timeout_seconds: float = 10.0,
                 default_to_address: list[str] | None = None
    ):
        self._authenticator = authenticator
        self._from_address = from_address
        self._timeout_seconds = timeout_seconds
        self._default_to_address = default_to_address if default_to_address is not None else []

    @staticmethod
    def default(
        client_id: str,
        client_secret: str,
        tenant_id: str,
        from_address: str,
        timeout_seconds: float = 10.0,
        default_to_address: list[str] | None = None
    ):
        """Creates a default GraphMailSender with a standard Authenticator."""
        authenticator = _Authenticator(
            client_id=client_id,
            client_secret=client_secret,
            tenant_id=tenant_id,
            http_timeout_seconds=timeout_seconds
        )
        return GraphMailSender(
            authenticator=authenticator,
            from_address=from_address,
            timeout_seconds=timeout_seconds,
            default_to_address=default_to_address
        )

    def send(self, subject: str, body: str, to: str | None = None) -> None:
        """Sends a mail via Microsoft Graph API."""

        token = self._authenticator.get_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        recipients = (
            [{"emailAddress": {"address": to}}]
            if to is not None
            else [
                {"emailAddress": {"address": addr}} for addr in self._default_to_address
            ]
        )

        email_data: dict[str, Any] = {
            "message": {
                "subject": subject,
                "body": {
                    "contentType": "HTML",
                    "content": body
                },
                "toRecipients": recipients
            }
        }
        r = requests.post(f"https://graph.microsoft.com/v1.0/users/{self._from_address}/sendMail",
                          json=email_data,
                          headers=headers,
                          timeout=self._timeout_seconds)

        # we do not retry here: if we fail, alertmanager gets a non-200 response and will retry the webhook,
        # which is a more-stable retry behavior than retrying here (eg. due to unknown timeout of alertmanager's webhook client)
        r.raise_for_status()
