"""Utilities for Flask HTTP Server"""

import re
import hmac
from typing import Callable, ParamSpec, TypeVar
from flask import request, abort

P = ParamSpec("P")
R = TypeVar("R")

def static_bearer_auth(
    token: str,
    allow_anonymous: bool = False
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """
    Validates a Bearer token from the Authorization header
    to match a static value (shared-secret / API-Token).

    Params:
        token: The expected token value. If empty and allow_anonymous is True,
               no authentication will be performed.
        allow_anonymous: If True and token is empty, allows unauthenticated requests
               (ie. "always allow").
               Otherwise, interpret an empty token as invalid and always "401 Deny"
               (to make for a safe default).
    Returns:
        A decorator function to wrap Flask route handlers.
    """

    def always_allow_decorator(func: Callable[P, R]) -> Callable[P, R]:
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            return func(*args, **kwargs)
        return wrapper
    def safely_deny_decorator(_: Callable[P, R]) -> Callable[P, R]:
        def wrapper(*_args: P.args, **_kwargs: P.kwargs) -> R:
            abort(401)
        return wrapper
    if token == "":
        return safely_deny_decorator if not allow_anonymous else always_allow_decorator

    def with_token_decorator(func: Callable[P, R]) -> Callable[P, R]:

        # force ASCII to prevent utf-8 tricks
        # ignore case for "Bearer"
        regex_flags = re.ASCII | re.IGNORECASE
        bearer_pattern = re.compile(r'^Bearer\s+([A-Za-z0-9\-\._~\+/]+=*)$', regex_flags)

        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            auth_header = request.headers.get("Authorization", "")
            match = bearer_pattern.match(auth_header)

            if not match:
                abort(401)

            auth_header = match.group(1)

            # Use constant-time comparison to prevent timing attacks
            if not hmac.compare_digest(auth_header, token):
                abort(401)

            return func(*args, **kwargs)
        return wrapper

    return with_token_decorator
