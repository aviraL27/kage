"""Tests for Local PC Hardware Bridge tools."""

import platform
import pytest
from kage.tools.registry import registry
from kage.tools.pc_tools import get_pc_system_status


def test_pc_tools_registered():
    """Verify PC tools are in registry."""
    assert registry.get_tool("get_pc_system_status") is not None
    assert registry.get_tool("lock_workstation") is not None


def test_get_pc_system_status():
    """Verify get_pc_system_status returns valid dictionary."""
    status = get_pc_system_status()
    assert isinstance(status, dict)
    if platform.system() == "Windows":
        assert "device" in status or "error" in status
        if "device" in status:
            assert status["status"] == "online"
