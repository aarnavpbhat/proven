"""Network-off, enforced at runtime rather than promised in a README.

Financial data is sensitive, so Proven processes everything locally by default
and makes that structural: once `install()` runs, any attempt to open a
connection to anything other than this machine raises before a byte leaves the
process, and the attempt is recorded. The server installs it at start-up unless
it is launched with `--allow-network`, which is a deliberate act at the command
line rather than a setting someone can leave on.

Loopback stays allowed: the reviewer console is served on 127.0.0.1, and a
loopback connection cannot reach a third party.

The test suite runs under the same guard (`proven/tests/conftest.py`), so no
test can reach a provider either.
"""
from __future__ import annotations

import socket

_LOOPBACK = {"127.0.0.1", "::1", "localhost", "0.0.0.0", ""}

#: Destinations refused since the guard was installed.
BLOCKED: list[object] = []

_state = {"installed": False, "network_allowed": False}


class NetworkBlocked(RuntimeError):
    """Something tried to reach a host other than this machine while network was off."""


def _is_local(address: object) -> bool:
    host = str(address[0]) if isinstance(address, tuple) and address else str(address)
    return host in _LOOPBACK or host.startswith("127.")


def install() -> None:
    """Refuse every non-loopback connection from now on. Idempotent."""
    if _state["installed"]:
        return
    base_socket = socket.socket
    base_getaddrinfo = socket.getaddrinfo
    base_create_connection = socket.create_connection

    class GuardedSocket(base_socket):  # type: ignore[misc,valid-type]
        def connect(self, address):  # noqa: D102
            if not _is_local(address):
                BLOCKED.append(address)
                raise NetworkBlocked(f"network is off: refused connect to {address!r}")
            return super().connect(address)

        def connect_ex(self, address):  # noqa: D102
            if not _is_local(address):
                BLOCKED.append(address)
                raise NetworkBlocked(f"network is off: refused connect to {address!r}")
            return super().connect_ex(address)

    def guarded_getaddrinfo(host, port, *args, **kwargs):
        if not _is_local((host, port)):
            BLOCKED.append((host, port))
            raise NetworkBlocked(f"network is off: refused to resolve {host!r}")
        return base_getaddrinfo(host, port, *args, **kwargs)

    def guarded_create_connection(address, *args, **kwargs):
        if not _is_local(address):
            BLOCKED.append(address)
            raise NetworkBlocked(f"network is off: refused connection to {address!r}")
        return base_create_connection(address, *args, **kwargs)

    socket.socket = GuardedSocket  # type: ignore[misc]
    socket.getaddrinfo = guarded_getaddrinfo  # type: ignore[assignment]
    socket.create_connection = guarded_create_connection  # type: ignore[assignment]
    _state["installed"] = True
    _state["network_allowed"] = False


def allow_network() -> None:
    """Declare that this process may reach the network. Only valid before `install()`."""
    if _state["installed"]:
        raise RuntimeError("network was switched off for this process and cannot be re-enabled")
    _state["network_allowed"] = True


def network_allowed() -> bool:
    """True only if this process explicitly allowed the network and the guard is not installed."""
    return bool(_state["network_allowed"]) and not _state["installed"]


def installed() -> bool:
    """Whether the guard is active in this process."""
    return bool(_state["installed"])
