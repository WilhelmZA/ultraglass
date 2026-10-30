"""Validate RPKI state via Cloudflare GraphQL API."""

# Standard Library
import pickle
import typing as t
from concurrent.futures import ThreadPoolExecutor

# Third Party
import httpx

# Project
from hyperglass.log import log
from hyperglass.state import use_state
from hyperglass.external._base import BaseExternal

if t.TYPE_CHECKING:
    from ipaddress import IPv4Address, IPv6Address

    Prefix = t.Union[IPv4Address, IPv6Address, str]

# Maps normalized (lower-case, separators stripped) backend state names to the
# integer states hyperglass uses internally.
RPKI_STATE_MAP = {
    "invalid": 0,
    "valid": 1,
    "notfound": 2,
    "unknown": 2,
    "default": 3,
}
# Canonical integer -> display name, kept stable for logging.
RPKI_NAME_MAP = {0: "Invalid", 1: "Valid", 2: "NotFound", 3: "DEFAULT"}
CACHE_KEY = "hyperglass.external.rpki"
# Upper bound on concurrent uncached lookups for one batch.
RPKI_MAX_CONCURRENCY = 16
CLOUDFLARE_URL = "https://rpki.cloudflare.com"
CLOUDFLARE_QUERY = 'query GetValidation {{ validation(prefix: "{}", asn: {}) {{ state }} }}'


def _normalize_state(value: str) -> int:
    """Normalize a backend RPKI state string to an internal integer state."""
    key = str(value).strip().lower().replace("-", "").replace("_", "")
    return RPKI_STATE_MAP.get(key, 3)


def _cache_item(
    prefix: "Prefix", asn: t.Union[int, str], backend: str, rpki_server_url: str
) -> str:
    """Build the cache item for a prefix/origin pair and validator."""
    # A provider switch must not reuse a different validator's result.
    provider = backend if backend != "routinator" else f"{backend}:{rpki_server_url.rstrip('/')}"
    return f"{provider}:{prefix!s}@{asn!s}"


def _query_cloudflare(client: BaseExternal, prefix: "Prefix", asn: t.Union[int, str]) -> str:
    """Query one prefix/origin pair with an open Cloudflare session."""
    query = CLOUDFLARE_QUERY.format(prefix, asn)
    log.bind(query=query).debug("Cloudflare RPKI GraphQL Query")
    response = client._post("/api/graphql", data={"query": query})
    return response["data"]["validation"]["state"]


def _query_routinator(
    get: t.Callable[..., httpx.Response],
    rpki_server_url: str,
    prefix: "Prefix",
    asn: t.Union[int, str],
) -> str:
    """Query one prefix/origin pair with a Routinator HTTP GET callable."""
    url = f"{rpki_server_url.rstrip('/')}/validity"
    log.bind(url=url).debug("Routinator RPKI HTTP Query")
    response = get(url, params={"asn": str(asn), "prefix": str(prefix)}, timeout=5)
    response.raise_for_status()
    return response.json()["validated_route"]["validity"]["state"]


def rpki_state(
    prefix: "Prefix",
    asn: t.Union[int, str],
    backend: str = "cloudflare",
    rpki_server_url: str = "",
) -> int:
    """Get RPKI state and map to expected integer."""
    _log = log.bind(prefix=prefix, asn=asn)
    _log.debug("Validating RPKI State")

    cache = use_state("cache")
    state = 3
    ro = _cache_item(prefix, asn, backend, rpki_server_url)

    cached = cache.get_map(CACHE_KEY, ro)
    if cached is not None:
        state = cached
    else:
        try:
            if backend == "cloudflare":
                with BaseExternal(base_url=CLOUDFLARE_URL) as client:
                    validation_state = _query_cloudflare(client, prefix, asn)
            elif backend == "routinator":
                validation_state = _query_routinator(httpx.get, rpki_server_url, prefix, asn)
            else:
                raise ValueError(f"Unknown RPKI backend: {backend}")

            state = _normalize_state(validation_state)
            cache.set_map_item(CACHE_KEY, ro, state)
        except Exception as err:
            log.error(err)
            state = 3

    msg = "RPKI Validation State for {} via AS{} is {}".format(prefix, asn, RPKI_NAME_MAP[state])
    if cached is not None:
        msg += " [CACHED]"
    log.debug(msg)
    return state


def rpki_states(
    pairs: t.Iterable[t.Tuple["Prefix", t.Union[int, str]]],
    backend: str = "cloudflare",
    rpki_server_url: str = "",
    max_concurrency: int = RPKI_MAX_CONCURRENCY,
) -> t.Dict[t.Tuple[str, str], int]:
    """Get RPKI states for many prefix/origin pairs in one batch.

    Pairs are deduplicated, cached states come from one Redis read, and the
    uncached pairs are looked up concurrently (bounded by `max_concurrency`)
    over one HTTP session with one connection test. The result maps
    `(str(prefix), str(asn))` to the integer state.
    """
    if backend not in ("cloudflare", "routinator"):
        raise ValueError(f"Unknown RPKI backend: {backend}")

    unique = list(dict.fromkeys((str(prefix), str(asn)) for prefix, asn in pairs))
    if not unique:
        return {}

    cache = use_state("cache")
    cache_name = cache.key(CACHE_KEY)
    items = [_cache_item(prefix, asn, backend, rpki_server_url) for prefix, asn in unique]
    states: t.Dict[t.Tuple[str, str], int] = {}
    uncached: t.List[t.Tuple[t.Tuple[str, str], str]] = []

    for pair, item, raw in zip(unique, items, cache.instance.hmget(cache_name, items)):
        if raw is None:
            uncached.append((pair, item))
        else:
            states[pair] = pickle.loads(raw)  # noqa: S301 values are written by set_map_item

    log.bind(total=len(unique), cached=len(states), uncached=len(uncached)).debug(
        "Validating RPKI states in batch"
    )

    if uncached:
        found = _lookup_uncached(
            [pair for pair, _ in uncached], backend, rpki_server_url, max(1, max_concurrency)
        )
        with cache.pipeline() as pipeline:
            for pair, item in uncached:
                state = found.get(pair)
                if state is None:
                    states[pair] = 3
                else:
                    states[pair] = state
                    pipeline.set_map_item(CACHE_KEY, item, state)

    return states


def _lookup_uncached(
    pairs: t.List[t.Tuple[str, str]],
    backend: str,
    rpki_server_url: str,
    max_concurrency: int,
) -> t.Dict[t.Tuple[str, str], int]:
    """Look up uncached pairs concurrently over one session.

    Failed lookups are left out of the result so they are not cached.
    """
    found: t.Dict[t.Tuple[str, str], int] = {}

    def run(query: t.Callable[[str, str], str]) -> None:
        def one(pair: t.Tuple[str, str]) -> None:
            try:
                found[pair] = _normalize_state(query(*pair))
            except Exception as err:
                log.bind(prefix=pair[0], asn=pair[1]).error(err)

        with ThreadPoolExecutor(max_workers=min(max_concurrency, len(pairs))) as pool:
            list(pool.map(one, pairs))

    try:
        if backend == "cloudflare":
            with BaseExternal(base_url=CLOUDFLARE_URL) as client:
                run(lambda prefix, asn: _query_cloudflare(client, prefix, asn))
        else:
            with httpx.Client() as client:
                run(lambda prefix, asn: _query_routinator(client.get, rpki_server_url, prefix, asn))
    except Exception as err:
        log.error(err)

    return found
