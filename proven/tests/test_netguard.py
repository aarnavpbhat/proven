"""Network-off is enforced, not documented. Run in a fresh interpreter so nothing leaks."""
import subprocess
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def run_snippet(code: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-c", textwrap.dedent(code)], cwd=ROOT,
                          capture_output=True, text=True, timeout=60)


def test_outbound_connections_are_refused_and_loopback_is_not():
    result = run_snippet("""
        import socket, threading
        from proven import netguard
        netguard.install()
        try:
            socket.create_connection(("api.anthropic.com", 443), timeout=2)
            print("LEAKED")
        except netguard.NetworkBlocked:
            print("blocked-dns")
        try:
            s = socket.socket(); s.connect(("8.8.8.8", 53)); print("LEAKED")
        except netguard.NetworkBlocked:
            print("blocked-connect")
        server = socket.socket(); server.bind(("127.0.0.1", 0)); server.listen(1)
        port = server.getsockname()[1]
        client = socket.create_connection(("127.0.0.1", port), timeout=2)
        print("loopback-ok")
        print("network_allowed", netguard.network_allowed())
        try:
            netguard.allow_network(); print("REOPENED")
        except RuntimeError:
            print("cannot-reopen")
    """)
    out = result.stdout.split()
    assert result.returncode == 0, result.stderr
    assert "LEAKED" not in out and "REOPENED" not in out
    assert {"blocked-dns", "blocked-connect", "loopback-ok", "cannot-reopen"} <= set(out)
    assert "False" in out


def test_the_tests_themselves_run_with_the_guard_installed():
    from proven import netguard
    assert netguard.installed() and not netguard.network_allowed()


def test_installing_twice_is_harmless_and_still_blocks():
    result = run_snippet("""
        import socket
        from proven import netguard
        netguard.install()
        netguard.install()
        try:
            socket.create_connection(("example.com", 80), timeout=2)
            print("LEAKED")
        except netguard.NetworkBlocked:
            print("blocked")
    """)
    assert result.returncode == 0, result.stderr
    assert result.stdout.split() == ["blocked"]
