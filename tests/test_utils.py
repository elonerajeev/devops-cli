"""Tests for utility functions."""

import pytest
from devops_cli.utils.output import (
    status_badge,
    create_table,
)


class TestOutputUtils:
    """Test output utility functions."""

    def test_status_badge_healthy(self):
        """Test healthy status badge."""
        badge = status_badge("healthy")
        assert "HEALTHY" in badge
        assert "green" in badge

    def test_status_badge_unhealthy(self):
        """Test unhealthy status badge."""
        badge = status_badge("unhealthy")
        assert "UNHEALTHY" in badge
        assert "red" in badge

    def test_status_badge_running(self):
        """Test running status badge."""
        badge = status_badge("running")
        assert "RUNNING" in badge

    def test_status_badge_unknown(self):
        """Test unknown status badge."""
        badge = status_badge("something_else")
        assert "SOMETHING_ELSE" in badge

    def test_create_table(self):
        """Test table creation."""
        table = create_table("Test Table", [("Col1", "cyan"), ("Col2", "dim")])
        assert table is not None
        assert table.title == "Test Table"
