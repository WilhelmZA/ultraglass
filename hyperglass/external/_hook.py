"""Shared session handler for webhook providers."""

# Standard Library
import typing as t

# Local
from ._base import BaseExternal

if t.TYPE_CHECKING:
    # Project
    from hyperglass.models.config.logging import Http


class WebhookBase(BaseExternal, name="WebhookBase"):
    """Apply the `logging.http` request settings to a webhook session."""

    def __init__(self: "WebhookBase", config: "Http", base_url: str, parse: bool = True) -> None:
        """Initialize the session with the configured TLS, timeout and authentication."""
        super().__init__(
            base_url=base_url,
            config=config,
            verify_ssl=config.verify_ssl,
            timeout=config.timeout,
            parse=parse,
            auth=config.request_auth(),
        )

    async def _send_payload(self: "WebhookBase", data: t.Dict[str, t.Any]) -> t.Any:
        """POST a payload with the configured headers and URL parameters."""
        return await self._apost(
            endpoint=self.config.host.path or "",
            headers=self.config.request_headers(),
            params=self.config.params,
            data=data,
        )
