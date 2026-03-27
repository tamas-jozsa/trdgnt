"""
Tests for TICKET-035: SSL global monkey-patch removed from alpaca_bridge.

Verifies that importing alpaca_bridge no longer mutates requests.Session.__init__
for the entire process.
"""

import requests
import pytest


class TestNoGlobalSslMonkeyPatch:

    def test_importing_alpaca_bridge_does_not_patch_session(self):
        """
        After TICKET-035 fix: requests.Session.__init__ must be the original
        unpatched method after importing alpaca_bridge.
        """
        original_init = requests.Session.__init__

        import alpaca_bridge  # noqa: F401 — import is the test

        assert requests.Session.__init__ is original_init, (
            "requests.Session.__init__ was monkey-patched by alpaca_bridge import. "
            "This is the TICKET-035 regression. The global SSL patch must be removed."
        )

    def test_new_session_has_default_verify_true(self):
        """
        A freshly created requests.Session should have verify=True (default).
        If the monkey-patch were still present, verify would be False.
        """
        import alpaca_bridge  # noqa: F401

        s = requests.Session()
        assert s.verify is True, (
            f"requests.Session().verify == {s.verify!r} — expected True. "
            "The global SSL patch may still be active."
        )

    def test_alpaca_bridge_does_not_set_ssl_context_override(self):
        """
        Importing alpaca_bridge must not change ssl._create_default_https_context.
        We capture the value before and after import and assert it is unchanged.
        """
        import ssl
        # Note: if another library has already set this, we capture that as the
        # baseline — we only care that alpaca_bridge itself doesn't change it.
        before = ssl._create_default_https_context
        import alpaca_bridge  # noqa: F401
        after = ssl._create_default_https_context
        assert before is after, (
            "ssl._create_default_https_context was changed by alpaca_bridge import — "
            "TICKET-035 regression."
        )
