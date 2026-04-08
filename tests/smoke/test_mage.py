"""
Smoke tests for mage task runner.

These tests verify that mage targets can be listed.
"""

import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def test_mage_list():
    """Test that mage can list targets."""
    result = subprocess.run(
        ["mage", "-l"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True
    )
    # Mage may not be installed, so skip if not found
    if result.returncode != 0 and "not found" in result.stderr.lower():
        import pytest
        pytest.skip("mage not installed")
    
    assert result.returncode == 0, f"mage -l failed: {result.stderr}"
    assert "trading:once" in result.stdout


def test_mage_help():
    """Test that mage help works."""
    result = subprocess.run(
        ["mage", "help"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True
    )
    if result.returncode != 0 and "not found" in result.stderr.lower():
        import pytest
        pytest.skip("mage not installed")
    
    assert result.returncode == 0, f"mage help failed: {result.stderr}"
