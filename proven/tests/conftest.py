"""The product's own runtime guard, used on its own test suite.

Every Proven test runs with the network switched off by `proven.netguard` — the
same code the server installs at start-up — so a test that tried to reach a
provider would fail rather than spend money. The Claude extractor is tested
against a fake client; its network check is monkeypatched where a test needs it.
"""
import pytest

from proven import claims, netguard

netguard.install()


@pytest.fixture(autouse=True)
def _no_learned_terms_leak():
    """A console that starts with lessons on disk applies them process-wide (that is the
    point of it); no test may leave any behind for the next one."""
    yield
    claims.set_learned([])


def pytest_report_header(config):  # noqa: ARG001
    """Say in the run header that the guard is on, so nobody has to take it on trust."""
    return "proven: network off (proven.netguard installed for this session)"
