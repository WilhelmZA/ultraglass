# Dell OS10 query validation

Validated version: SmartFabric OS10 10.6.1.3P1, build 10.6.1.3P1.6, S5224F-VM. The query matrix covers default and LAB VRFs with text and structured output.

Apply `startup.cfg` from configuration mode. Connect separate BGP peers to `ethernet1/1/1` and `ethernet1/1/2`. Management SSH uses `mgmt1/1/1`; retain its configured address and credentials.

| Context | Interface | Device addresses | Peer addresses | Advertised prefixes | Origin AS |
|---|---|---|---|---|---|
| default | `ethernet1/1/1` | `10.250.1.1/24`, `fd00:250:1::1/64` | `10.250.1.2`, `fd00:250:1::2` | `1.0.0.0/24`, `2606:4700:4700::/48` | 13335 |
| LAB | `ethernet1/1/2` | `10.250.2.1/24`, `fd00:250:2::1/64` | `10.250.2.2`, `fd00:250:2::2` | `198.51.100.0/24`, `2001:db8:100::/48` | 64497 |

OS10 uses AS65030. Each peer uses AS65000 and one IPv4 BGP session carrying both address families. Set the advertised next hop to the corresponding peer address. Advertise community `65000:777` and MED 42. Confirm one received prefix per family with `show ip bgp [vrf LAB] [ipv6 unicast] summary`.

Configure Ultraglass with `platform: dell_os10`. Set `attrs.source4` and `attrs.source6` to the context's device addresses. Set `vrf: LAB` on the LAB entry. Both output modes use the following SSH timing settings:

```yaml
driver_config:
  fast_cli: false
  global_delay_factor: 1
  conn_timeout: 30
  banner_timeout: 60
  auth_timeout: 60
  read_timeout_override: 90
```

Wait for OS10 services to finish starting before checking admin login. The validated configuration cancels zero-touch deployment with `ztd cancel` and saves with `copy running-configuration startup-configuration`.

## Query matrix

Each context has seven cases per mode: IPv4/IPv6 prefix queries, one community query covering both families, IPv4/IPv6 ping and IPv4/IPv6 traceroute. All 28 CLI cases, 28 uncached HTTP API comparisons and 28 browser queries pass. API checks assert exact prefixes, AS paths, next hops, peer IDs, communities, best-path state, metric, local preference, weight, VRF labels and populated traceroute hops. Browser checks verify route tables, community menus, traceroute tables and native text with no page errors.

The four cross-VRF prefix queries return no routes. The 26 command captures and manifest are in `hyperglass/plugins/tests/fixtures/dell-os10-live/`.

## Restricted-table profile

The restricted feed caps the default VRF at 10,000 prefixes per address family. The received table contains 10,000 IPv4 and 9,729 IPv6 routes; LAB retains one prefix per family. Prefix checks use `1.0.0.0/24` and `2001:4860::/32`. Their observed AS paths are `65000 37239 13335` and `65000 37497 15169`. Two control prefixes, `198.18.74.0/24` and `2001:db8:74::/48`, carry community `65000:777` for bounded community searches.

For slow CLI session initialization, set `request_timeout: 240` in `config.yaml` and `driver_config.read_timeout_override: 180` on the device. These settings allow session initialization and command execution to finish within the browser request timeout.

The restricted-table matrix passes all 28 CLI queries, 28 uncached API comparisons and 28 browser queries with no page errors. Browser checks use a dedicated query account. Interrupted checks resume from saved results; the completed matrix is not a single uninterrupted run. The original small-table captures remain the regression fixtures.

## Coverage limits

Completed matrices cover both the small-table and restricted-table profiles above. Direct pings reach each data gateway; application diagnostics target each context's own interface address. Traceroute validates one-hop execution and parsing, not remote routed forwarding. Community summaries remain text. AS-path searches use custom directives with configured filter lists.

A separate full-table run converges at 1,094,724 IPv4 and 261,579 IPv6 prefixes from a RIPE RIS rrc19 snapshot. OS10 reports two IPv4 prefixes rejected for invalid AS-path length. After adding two community-query control prefixes, 25 of 28 CLI cases pass before management access stops responding. Subsequent SSH retries fail, so full-table API and browser acceptance remains incomplete. This result does not establish sustained full-table capacity.
