"""Lightweight HTTP health check server for Render and UptimeRobot monitoring."""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional

from kage.config import settings

logger = logging.getLogger(__name__)


class HealthCheckHandler(BaseHTTPRequestHandler):
    """HTTP handler responding to health probes on /, /health, and /ping."""

    def do_GET(self) -> None:
        """Handle GET requests."""
        if self.path in ("/", "/health", "/ping"):
            payload = {
                "status": "ok",
                "service": "kage",
                "version": "1.0.0",
                "timezone": settings.timezone_name,
                "timestamp": datetime.now(settings.tz).isoformat(),
            }
            body = json.dumps(payload).encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            body = b'{"error": "Not Found"}'
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        """Suppress default HTTP access logging noise unless in debug mode."""
        logger.debug("%s - - [%s] %s", self.address_string(), self.log_date_time_string(), format % args)


def start_health_server(port: Optional[int] = None, host: str = "0.0.0.0") -> ThreadingHTTPServer:
    """Start the health check HTTP server in a background daemon thread."""
    if port is None:
        port = int(os.environ.get("PORT", "8000"))

    server = ThreadingHTTPServer((host, port), HealthCheckHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True, name="health-check-server")
    thread.start()
    logger.info(f"Health check HTTP server listening on http://{host}:{port}/health")
    return server
