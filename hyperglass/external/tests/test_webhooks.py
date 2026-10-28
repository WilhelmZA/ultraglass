"""Test webhook payloads and delivery to a local receiver."""

# Standard Library
import json
import asyncio
import threading
from datetime import UTC, datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

# Third Party
import pytest

# Project
from hyperglass.models.webhook import Webhook
from hyperglass.models.config.logging import Http

# Local
from ..generic import GenericHook

QUERY = {
    "query_location": "lab-frr",
    "query_type": "bgp_route",
    "query_target": "1.1.1.1",
    "headers": {"user-agent": "pytest"},
    "source": "192.0.2.10",
    "network": {"prefix": "192.0.2.0/24", "asn": "64496"},
    "timestamp": datetime.now(UTC),
}


@pytest.mark.parametrize("provider", ("slack", "msteams", "export_dict"))
def test_webhook_payload(provider):
    webhook = Webhook(**QUERY)

    assert getattr(webhook, provider)()
    assert webhook.network.asn == "64496"


def test_webhook_localhost_resets_network():
    webhook = Webhook(**{**QUERY, "source": "127.0.0.1"})

    assert webhook.network.asn == "Unknown"


def test_generic_webhook_uses_url_port():
    received = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            received.append((self.path, json.loads(self.rfile.read(int(self.headers["Content-Length"])))))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"{}")

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        config = Http(provider="generic", host=f"http://127.0.0.1:{server.server_port}/hook")

        async def send():
            async with GenericHook(config) as hook:
                await hook.send(query=QUERY)

        asyncio.run(send())
    finally:
        server.shutdown()

    assert received[0][0] == "/hook"
    assert received[0][1]["query_target"] == "1.1.1.1"
