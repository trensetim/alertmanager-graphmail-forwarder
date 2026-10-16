"""
    Debug aid: watches the TLS certificate and key files via inotify and logs when they change.

    This does not reload anything itself: gunicorn's sync worker already reads the files
    for every accepted connection (see `TlsConfiguration.load_ssl_context`).
    It only makes rotations (eg. by cert-manager) visible in the logs.

    Impl Note: we watch the *parent directories*, not the files themselves:
    Kubernetes updates secret volumes by atomically swapping a `..data` symlink in the mount directory,
    and other tools replace files via rename -- both of which a watch on the old file inode would miss.
    Any event only triggers a re-read; a change is only logged if the file contents actually differ.
"""

import hashlib
import os
import ssl
import threading
from dataclasses import dataclass
from logging import Logger
from typing import Any

from inotify_simple import INotify, flags, Event  # type: ignore[import-untyped]

from config import TlsConfiguration

WATCH_MASK = (
    flags.CLOSE_WRITE
    | flags.MOVED_TO
    | flags.MOVED_FROM
    | flags.CREATE
    | flags.DELETE
    | flags.ATTRIB
    | flags.DELETE_SELF
    | flags.MOVE_SELF
)
"""Directory events after which the TLS files may have changed."""
COALESCE_DELAY_MS = 500
"""Wait this long after the first event before re-reading, so that eg. a cert+key swap is seen as one change."""

@dataclass(frozen=True)
class State:
    """Snapshot of the TLS files on disk."""

    cert_digest: str
    """SHA-256 of the certificate file contents (None if unreadable)."""
    key_digest: str
    """SHA-256 of the key file contents (None if unreadable). Only used for change detection, never logged."""
    cert_fingerprint: str
    """SHA-256 fingerprint of the first (leaf) certificate, as shown by `openssl x509 -fingerprint -sha256` (not the SHA-1 default)."""

    def __eq__(self, value: Any):
        if not isinstance(value, State):
            return False
        return (
            self.cert_digest == value.cert_digest and
            self.key_digest == value.key_digest and
            self.cert_fingerprint == value.cert_fingerprint
        )

type StateOrError = State | str
"""Either the latest state of the tls files, or an error string."""

class TlsCertificateWatcher:
    """Watches the TLS certificate and key files and logs whenever they change."""

    config: TlsConfiguration
    logger: Logger
    last_state: StateOrError

    def __init__(self, config: TlsConfiguration, logger: Logger ):
        self.config = config
        self.logger = logger
        self.last_state = self._read_state()

    def start(self) -> threading.Thread | None:
        """
        Start a daemon thread that waits for inotify events.
        Returns the thread, or None if inotify is unavailable (the watcher is debug-only, so this is not fatal).
        """

        try:
            inotify = INotify()
            for directory in self._watched_directories():
                inotify.add_watch(directory, WATCH_MASK) # pyright: ignore[reportUnknownMemberType]

        except OSError as e:
            self.logger.warning("Cannot watch TLS files for changes (inotify unavailable: %s), skipping", e)
            return None

        thread = threading.Thread(target=self._watch, args=(inotify,), name="tls_watcher", daemon=True)
        thread.start()
        return thread

    def _watch(self, inotify: INotify) -> None:
        """While-True loop reading inotify"""
        with inotify:
            while inotify.closed is False:
                events: list[Event] = inotify.read(read_delay=COALESCE_DELAY_MS) # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]
                if any(e.mask & flags.IGNORED for e in events): # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
                    # a watched directory itself vanished (eg. unmounted): no more events will arrive for it
                    self.logger.warning("A watched TLS directory was removed, no longer watching TLS files for changes")
                    self._check()
                    return
                try:
                    self._check()
                except Exception: # pylint: disable=broad-exception-caught
                    self.logger.exception("Failed to check TLS files for changes")

    def _watched_directories(self) -> list[str]:
        """The (deduplicated) parent directories of the certificate and key files."""
        dirs = (os.path.dirname(os.path.abspath(p)) for p in (self.config.cert_path, self.config.key_path))
        return list(dict.fromkeys(dirs))

    def _read_state(self) -> StateOrError:
        """Read the current state of the TLS files from disk."""
        cert_bytes = _read_file(self.config.cert_path)
        key_bytes = _read_file(self.config.key_path)

        if cert_bytes is None or key_bytes is None:
            return "certificate or key file not readable"

        fingerprint = _fingerprint(cert_bytes)

        if fingerprint is None:
            return "unable to compute certificate fingerprint"

        try:
            self.config.load_ssl_context()
        except (ssl.SSLError, OSError) as e:
            return f"load_ssl_context failed: {e}"

        return State(
            cert_digest=hashlib.sha256(cert_bytes).hexdigest(),
            key_digest=hashlib.sha256(key_bytes).hexdigest(),
            cert_fingerprint=fingerprint
        )

    def _check(self) -> None:
        """Compare the files on disk against the last seen state and log any change."""
        state = self._read_state()
        previous = self.last_state
        self.last_state = state

        if state == previous:
            return # no change, no log, even if the error stays the same

        # new state is either: valid & different cert OR a different error than last time: logging both
        if isinstance(state, State):
            self.logger.info("TLS certificate changed. New SHA256 fingerprint=%s", state.cert_fingerprint)
            self.logger.debug("New TLS cert/key digests: %s / %s", state.cert_digest, state.key_digest)
        else:
            self.logger.warning("TLS files not readable or invalid: %s", state)


def _read_file(path: str) -> bytes | None:
    try:
        with open(path, "rb") as f:
            return f.read()
    except OSError:
        return None

def _fingerprint(cert_bytes_pem: bytes) -> str | None:
    """
    SHA-256 fingerprint of the first (ie. leaf) certificate in the PEM file,
    equal to `openssl x509 -noout -fingerprint -sha256` (note: openssl defaults to SHA-1 without `-sha256`).
    """
    pem = cert_bytes_pem.decode("ascii", errors="replace")
    start = pem.find(ssl.PEM_HEADER)
    end = pem.find(ssl.PEM_FOOTER, start)
    if start < 0 or end < 0:
        return None
    try:
        # only pass the first block: the file may contain the whole chain
        der = ssl.PEM_cert_to_DER_cert(pem[start:end + len(ssl.PEM_FOOTER)])
        return ":".join(f"{b:02X}" for b in hashlib.sha256(der).digest())
    except ValueError:
        return None
