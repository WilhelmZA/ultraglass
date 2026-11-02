# Dell OS10 live captures

Captured over authenticated SSH from SmartFabric OS10 10.6.1.3P1, build 10.6.1.3P1.6, S5224F-VM, on 2026-11-02. `version.txt` identifies the appliance. `manifest.json` records all 26 commands. Sanitization removes trailing whitespace only.

| Context | IPv4 prefix | IPv6 prefix | AS path | Next hops |
|---|---|---|---|---|
| default | `1.0.0.0/24` | `2606:4700:4700::/48` | `65000 13335` | `10.250.1.2`, `fd00:250:1::2` |
| LAB | `198.51.100.0/24` | `2001:db8:100::/48` | `65000 64497` | `10.250.2.2`, `fd00:250:2::2` |

One BGP session per VRF carries both address families. Each family has one prefix with community `65000:777` and MED 42. These are small-table functional checks, not full-table load tests. BGP summaries record the received prefix counts. `vrfs.txt` records interface placement.

OS10 prints `Default-IP-Routing-Table` in both routing contexts. Ultraglass uses the configured device VRF to label results. Communities appear below the `Communities:` heading. Tests verify route attributes, command construction, text preservation and malformed-response fallback. Synthetic malformed-response cases are identified in the test names.

The four `negative` captures query prefixes belonging to the other VRF and return `%Error: Prefix does not exist.`. Community queries return family-specific summaries and remain text. OS10 AS-path searches require configured filter lists and are not exposed as arbitrary regular-expression built-ins.

Direct gateway pings pass with five replies. Traceroute targets each VRF's own interface address and returns one probe at one hop. This verifies command execution, VRF selection and parsing, not remote routed forwarding.

Live acceptance passes 28 CLI queries, 28 uncached API comparisons and 28 browser queries across both routing contexts and output modes. See `lab/configs/os10/README.md` for setup and the query matrix.
