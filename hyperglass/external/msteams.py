"""Session handler for Microsoft Teams API."""

# Standard Library
import typing as t

# Project
from hyperglass.log import log
from hyperglass.models.webhook import Webhook
from hyperglass.external._hook import WebhookBase

if t.TYPE_CHECKING:
    # Project
    from hyperglass.models.config.logging import Http


class MSTeams(WebhookBase, name="MSTeams"):
    """Microsoft Teams session handler."""

    def __init__(self: "MSTeams", config: "Http") -> None:
        """Initialize external base class with Microsoft Teams connection details."""

        super().__init__(config=config, base_url="https://outlook.office.com", parse=False)

    async def send(self: "MSTeams", query: t.Dict[str, t.Any]):
        """Send an incoming webhook to Microsoft Teams."""

        payload = Webhook(**query)
        log.bind(destination="MS Teams", payload=payload).debug("Sending request")

        return await self._send_payload(payload.msteams())
