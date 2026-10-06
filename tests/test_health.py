"""Tests for health check HTTP server."""

from __future__ import annotations

import json
import urllib.request
import pytest

from kage.web.health import start_health_server


def test_health_check_endpoint():
    """Verify HTTP health server responds with 200 on /health and /."""
    # Start on test port 8099
    server = start_health_server(port=8099, host="127.0.0.1")

    try:
        # Test /health
        with urllib.request.urlopen("http://127.0.0.1:8099/health") as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data["status"] == "ok"
            assert data["service"] == "kage"
            assert "timestamp" in data

        # Test /
        with urllib.request.urlopen("http://127.0.0.1:8099/") as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data["status"] == "ok"

        # Test /ping
        with urllib.request.urlopen("http://127.0.0.1:8099/ping") as resp:
            assert resp.status == 200

        # Test 404
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen("http://127.0.0.1:8099/unknown")
        assert exc_info.value.code == 404

    finally:
        server.shutdown()
