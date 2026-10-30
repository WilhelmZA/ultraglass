"""Custom exceptions for hyperglass."""

# Standard Library
import json as _json
import string
from typing import Any, Set, Dict, List, Union, Literal, Optional

# Third Party
from pydantic import ValidationError

# Project
from hyperglass.log import log
from hyperglass.util import repr_from_attrs
from hyperglass.constants import STATUS_CODE_MAP

ErrorLevel = Literal["danger", "warning"]


class _BlankingFormatter(string.Formatter):
    """String formatter that renders unknown placeholders as empty strings."""

    def get_value(self, key: Union[int, str], args: Any, kwargs: Dict[str, Any]) -> Any:
        """Return the value for a placeholder, or an empty string if it is unknown."""
        if isinstance(key, str):
            return kwargs.get(key, "")
        return args[key] if key < len(args) else ""

    def get_field(self, field_name: str, args: Any, kwargs: Dict[str, Any]) -> Any:
        """Resolve a placeholder, blanking it if attribute or index access fails."""
        try:
            return super().get_field(field_name, args, kwargs)
        except (AttributeError, IndexError, KeyError, TypeError, ValueError):
            return "", field_name


class HyperglassError(Exception):
    """hyperglass base exception."""

    def __init__(
        self,
        message: str = "",
        level: ErrorLevel = "warning",
        keywords: Optional[List[str]] = None,
    ) -> None:
        """Initialize the hyperglass base exception class."""
        self._message = message
        self._level = level
        self._keywords = keywords or []
        if self._level == "warning":
            log.error(str(self))
        elif self._level == "danger":
            log.critical(str(self))
        else:
            log.info(str(self))

    def __str__(self) -> str:
        """Return the instance's error message."""
        return self._message

    def __repr__(self) -> str:
        """Return the instance's severity & error message in a string."""
        return repr_from_attrs(self, ("_message", "level", "keywords"), strip="_")

    def dict(self) -> Dict[str, Union[str, List[str]]]:
        """Return the instance's attributes as a dictionary."""
        return {
            "message": self._message,
            "level": self._level,
            "keywords": self.keywords,
        }

    def json(self) -> str:
        """Return the instance's attributes as a JSON object."""
        return _json.dumps(self.__dict__())

    @staticmethod
    def _safe_format(template: str, **kwargs: Any) -> str:
        """Safely format a string template from keyword arguments.

        Placeholders with no matching keyword argument are blanked. If the
        template cannot be parsed at all, it is returned unchanged. This
        method never raises.
        """
        try:
            return _BlankingFormatter().vformat(
                str(template), (), {k: str(v) for k, v in kwargs.items()}
            )
        except Exception:  # noqa: BLE001
            return str(template)

    def _parse_pydantic_errors(*errors: Dict[str, Any]) -> str:
        errs = ("\n",)

        for err in errors:
            loc = " → ".join(str(loc) for loc in err["loc"])
            errs += (f"Field: {loc}\n  Error: {err['msg']}\n",)

        return "\n".join(errs)

    def _process_keywords(self) -> None:
        out: Set[str] = set()
        for val in self._keywords:
            if isinstance(val, str):
                out.add(val)
            elif isinstance(val, list):
                for v in val:
                    out.add(v)
            else:
                out.add(str(val))
        self._keywords = list(out)

    @property
    def message(self) -> str:
        """Return the instance's `message` attribute."""
        return self._message

    @property
    def level(self) -> str:
        """Return the instance's `level` attribute."""
        return self._level

    @property
    def keywords(self) -> List[str]:
        """Return the instance's `keywords` attribute."""
        self._process_keywords()
        return self._keywords

    @property
    def status_code(self) -> int:
        """Return HTTP status code based on level level."""
        return STATUS_CODE_MAP.get(self._level, 500)


class PublicHyperglassError(HyperglassError):
    """Base exception class for user-facing errors.

    Error text should be defined in
    `hyperglass.configuration.params.messages` and associated with the
    exception class at start time.
    """

    _level = "warning"
    _message_template = "Something went wrong."
    _original_template_name: str = ""

    def __init_subclass__(
        cls, *, template: Optional[str] = None, level: Optional[ErrorLevel] = None
    ) -> None:
        """Override error attributes from subclass."""

        if template is not None:
            cls._message_template = template
            cls._original_template_name = template
        if level is not None:
            cls._level = level

    def __init__(self, **kwargs: str) -> None:
        """Format error message with keyword arguments."""
        # Project
        from hyperglass.state import use_state

        if "error" in kwargs:
            error = kwargs.pop("error")
            error = self._safe_format(str(error), **kwargs)
            kwargs["error"] = error

        template = self._message_template

        (messages := use_state("params").messages)
        if messages.has(self._original_template_name):
            template = messages[self._original_template_name]
        if "error" in kwargs and "({error})" not in template:
            template += " ({error})"
        self._message = self._safe_format(template, **kwargs)
        self._keywords = list(kwargs.values())
        super().__init__(message=self._message, level=self._level, keywords=self._keywords)


class PrivateHyperglassError(HyperglassError):
    """Base exception class for internal system errors.

    Error text is dynamic based on the exception being caught.
    """

    _level = "warning"

    def _parse_validation_error(self, err: ValidationError) -> str:
        errors = err.errors()
        parsed = {
            k: ", ".join(str(loc) for t in errors for loc in t["loc"] if t["type"] == k)
            for k in {e["type"] for e in errors}
        }
        return ", ".join(parsed.values())

    def __init_subclass__(cls, *, level: Optional[ErrorLevel] = None) -> None:
        """Override error attributes from subclass."""
        if level is not None:
            cls._level = level

    def __init__(self, message: str, **kwargs: Any) -> None:
        """Format error message with keyword arguments."""
        if "error" in kwargs:
            error = kwargs.pop("error")
            error = self._safe_format(str(error), **kwargs)
            kwargs["error"] = error

        if isinstance(message, ValidationError):
            message = self._parse_validation_error(message)

        self._message = self._safe_format(message, **kwargs)
        self._keywords = list(kwargs.values())
        super().__init__(message=self._message, level=self._level, keywords=self._keywords)
