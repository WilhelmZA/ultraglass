"""Session handler for Generic HTTP API endpoint."""

# Standard Library
import typing as t

# Project
from hyperglass.log import log
from hyperglass.models.webhook import Webhook

# Local
from ._hook import WebhookBase

if t.TYPE_CHECKING:
    # Project
    from hyperglass.models.config.logging import Http


class GenericHook(WebhookBase, name="Generic"):
    """Generic HTTP webhook session handler."""

    def __init__(self: "GenericHook", config: "Http") -> None:
        """Initialize external base class with http connection details."""

        super().__init__(config=config)

    async def send(self: "GenericHook", query: t.Dict[str, t.Any]):
        """Send an incoming webhook to http endpoint."""

        payload = Webhook(**query)
        log.bind(host=self.config.host.host, payload=payload).debug("Sending request")

        return await self._send_payload(payload.export_dict())
