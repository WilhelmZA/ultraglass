# Dell OS9 9.13 live captures

Captured over authenticated SSH from Dell OS9 9.13(0.0), S6000 emulator, on 2026-11-02. `version.txt` identifies the appliance. `manifest.json` records all 22 commands. Sanitization removes trailing whitespace only. The outputs come from the appliance, not reference documentation.

| Context | IPv4 prefix | IPv6 prefix | AS path | Next hops |
|---|---|---|---|---|
| default | `1.0.0.0/24` | `2606:4700:4700::/48` | `65000 13335` | `10.251.9.2`, `fd00:251:9::2` |
| LAB | `198.51.100.0/24` | `2001:db8:100::/48` | `65000 64497` | `10.254.2.2`, `fd00:254:2::2` |

Each context has one BGP session carrying both address families, with one prefix per family and community `65000:777`. The unused IPv6 transport neighbor in the default context remains administratively shut. `vrfs.txt` records interface placement. OS9 prints `Default-IP-Routing-Table` and `Default-MBGP-Routing-Table` even for LAB prefix details; Ultraglass labels these responses using the configured device VRF.

Route detail contains `Metric 4294967295 (Default)` and community values on the line after `Communities :`. The shared Dell parser previously returned this valid response as text. The regression suite verifies both route families and VRF labels, all captured route attributes, malformed-response fallback, native command construction, text preservation and traceroute parsing. The extra wrapped-community mutation is explicitly synthetic and verifies that another attribute's values do not become standard communities.

AS-path captures use `show ip bgp [vrf LAB] regexp _65000_` and contain only IPv4 routes. OS9 rejects the explicit `ipv4 unicast regexp` and `ipv6 unicast regexp` forms. Community captures contain separate family summaries and remain text. VRF ping uses `ping vrf LAB TARGET count 5`.

Direct pings reach the data-link gateways with 5/5 replies. Traceroute captures target the default VRF's own interface addresses and return one hop. They verify the native command and parser, not remote routed forwarding.

Acceptance checks pass in both output modes: 28 CLI queries, 28 uncached HTTP API comparisons and 28 browser queries. Default VRF has eight cases per mode; LAB has six because its traceroute is not advertised. Four negative controls query the other context's prefixes and return no routes. Test setup and SSH settings are documented in `lab/configs/os9/README.md`.
