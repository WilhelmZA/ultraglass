"""Join wrapped OS9 IPv6 RTT lines before standard traceroute parsing."""

# Standard Library
import re
import typing as t

# Local
from .trace_route_standard import TraceroutePluginStandard


class TraceroutePluginOS9(TraceroutePluginStandard):
    """Keep OS9 continuation handling scoped to the OS9 directive."""

    platforms: t.Sequence[str] = ("dell_force10",)
    directives: t.Sequence[str] = ("__hyperglass_dell_force10_traceroute__",)

    def process(self, *, output, query):
        """Preserve the original response when structured output is disabled."""
        text = output if isinstance(output, str) else "\n".join(output)
        normalized = re.sub(
            r"(^\s*\d+[ \t]+\S+)[ \t]*\n[ \t]+((?:\d+\.\d+[ \t]+ms[ \t]*){1,3})",
            r"\1 \2",
            text,
            flags=re.MULTILINE,
        )
        normalized = re.sub(r"^\d+ hops max[^\n]*\n?", "", normalized, flags=re.MULTILINE)
        result = super().process(output=(normalized,), query=query)
        if isinstance(result, (tuple, list, str)):
            return output
        result.raw_output = text
        return result
