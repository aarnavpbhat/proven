"""Proven's test suite: `python -m pytest proven/tests -q`.

Every test runs with the network switched off by `proven.netguard` (see
conftest.py). Negative controls — inputs that must *not* be flagged — sit beside
the positive cases in each file, because a check that flags sound work costs
more than it catches.
"""
