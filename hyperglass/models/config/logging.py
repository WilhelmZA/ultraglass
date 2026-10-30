"""Validate logging configuration."""

# Standard Library
import typing as t
from pathlib import Path

# Third Party
from pydantic import Field, ByteSize, SecretStr, AnyHttpUrl, DirectoryPath, field_validator

# Project
from hyperglass.constants import __version__

# Local
from ..main import HyperglassModel
from ..fields import LogFormat, HttpAuthMode, HttpProvider


class Syslog(HyperglassModel):
    """Validation model for syslog configuration."""

    enable: bool = True
    host: str
    port: int = 514


class HttpAuth(HyperglassModel):
    """HTTP hook authentication parameters."""

    mode: HttpAuthMode = "basic"
    username: t.Optional[str] = None
    password: SecretStr
    header: str = "x-api-key"

    def api_key(self):
        """Represent authentication as an API key header."""
        return {self.header: self.password.get_secret_value()}

    def basic(self):
        """Represent HTTP basic authentication."""
        return (self.username or "", self.password.get_secret_value())


class Http(HyperglassModel, extra="allow"):
    """HTTP logging parameters."""

    enable: bool = True
    provider: HttpProvider = "generic"
    host: AnyHttpUrl
    authentication: t.Optional[HttpAuth] = None
    headers: t.Dict[str, t.Union[str, int, bool, None]] = {}
    params: t.Dict[str, t.Union[str, int, bool, None]] = {}
    verify_ssl: bool = True
    timeout: t.Union[float, int] = 5.0

    @field_validator("headers", "params")
    def stringify_headers_params(cls, value):
        """Ensure headers and URL parameters are strings."""
        for k, v in value.items():
            if not isinstance(v, str):
                value[k] = str(v)
        return value

    def request_headers(self) -> t.Dict[str, str]:
        """Build the headers for a webhook request, including an API key header."""
        headers = {"user-agent": f"hyperglass/{__version__}", **self.headers}
        if self.authentication is not None and self.authentication.mode == "api_key":
            headers.update(self.authentication.api_key())
        return headers

    def request_auth(self) -> t.Optional[t.Tuple[str, str]]:
        """Build the HTTP basic authentication credentials for a webhook request."""
        if self.authentication is not None and self.authentication.mode == "basic":
            return self.authentication.basic()
        return None


class QuerySamples(HyperglassModel):
    """Structured request/response capture (raw + parsed) as JSON lines.

    When enabled, every query appends one JSON object to a JSONL file capturing
    the request, the raw device output, and the parsed result (and failures).
    Intended for shipping to Loki via Grafana Alloy and for building parser
    regression fixtures. Disabled by default.

    Note: raw output can contain internal addresses/communities/interface names.
    """

    enable: bool = False
    # Output file. Defaults to "<logging.directory>/hyperglass_query_log.jsonl".
    path: t.Optional[Path] = None
    include_raw: bool = True
    include_parsed: bool = True
    # Size-based rotation threshold.
    max_size: ByteSize = "50MB"
    # Rotated files kept as "<name>.1" (newest) to "<name>.<backup_count>".
    backup_count: int = Field(1, ge=1)


class Logging(HyperglassModel):
    """Validation model for logging configuration."""

    directory: DirectoryPath = Path("/tmp")  # noqa: S108
    format: LogFormat = "text"
    max_size: ByteSize = "50MB"
    syslog: t.Optional[Syslog] = None
    http: t.Optional[Http] = None
    samples: QuerySamples = Field(default_factory=QuerySamples)
    # Write each SSH session to "<directory>/<device id>-<YYYYMMDD>.log". Netmiko
    # redacts the device password and secret. Disabled by default.
    session_log: bool = False
