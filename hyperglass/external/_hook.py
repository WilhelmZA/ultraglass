"""Shared session handler for webhook providers."""

# Standard Library
import typing as t
from urllib.parse import parse_qsl

# Local
from ._base import BaseExternal

if t.TYPE_CHECKING:
    # Project
    from hyperglass.models.config.logging import Http


class WebhookBase(BaseExternal, name="WebhookBase"):
    """Apply the `logging.http` settings to a webhook session."""

    def __init__(self: "WebhookBase", config: "Http", parse: bool = True) -> None:
        """Initialize the session from the scheme, host and port of `logging.http.host`."""
        super().__init__(
            base_url=f"{config.host.scheme}://{config.host.host}:{config.host.port}",
            config=config,
            verify_ssl=config.verify_ssl,
            timeout=config.timeout,
            parse=parse,
            auth=config.request_auth(),
        )

    def _request_params(self: "WebhookBase") -> t.Dict[str, str]:
        """Merge the query string of `logging.http.host` with `logging.http.params`.

        Teams Workflows URLs carry their signature in the query string, so it must be kept.
        """
        params = dict(parse_qsl(self.config.host.query or "", keep_blank_values=True))
        params.update(self.config.params)
        return params

    async def _send_payload(self: "WebhookBase", data: t.Dict[str, t.Any]) -> t.Any:
        """POST a payload with the configured headers and URL parameters."""
        return await self._apost(
            endpoint=self.config.host.path or "",
            headers=self.config.request_headers(),
            params=self._request_params(),
            data=data,
        )
