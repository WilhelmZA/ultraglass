# Captured lab output

- `arista_aspath.json`: cEOS 4.36.3M, 27 October 2026, `show ip bgp regexp _13335$ | json`. Retains one complete route entry from 2,544 entries. No route fields are synthesized.
- `arista_traceroute.txt`: cEOS 4.36.3M, 27 October 2026, `traceroute ip 1.1.1.1 source 10.250.7.1`. Complete output, including MPLS annotations and multiple responders.
- `bird_traceroute.txt`, `openbgpd_traceroute.txt`, `vyos_traceroute.txt`: complete built-in traceroute responses from the corresponding lab devices, 27 October 2026, target `1.1.1.1`. Each capture includes all nine hops and the destination.

Synthetic cases in tests are explicitly separate from these device captures. Issues #22, #23 and #25 track the remaining hardware and configuration matrix.

## 28 October 2026 captures

Text fixtures retain all output lines and column spacing. Trailing end-of-line whitespace is removed from the Huawei text captures.

- `huawei-vrp/`: complete CE12800 V200R005C10SPC607B607 responses. `route4.txt` and `route6.txt` use `display bgp [ipv6] routing-table <target> | no-more` for `1.1.1.1` and `2606:4700::1111`. `aspath4.txt` and `aspath6.txt` use `display bgp [ipv6] routing-table regular-expression _13335$`. `community4.txt` and `community6.txt` use `display bgp [ipv6] routing-table community 37195:302`. `trace.txt` uses `tracert -w 500 -q 1 -f 1 -a 10.250.8.1 1.1.1.1`. The lab advertises a bounded route subset to this emulated control plane. Captures contain two IPv4 AS-path routes, one IPv6 AS-path route, 40 IPv4 community routes, and zero IPv6 community routes.
- Huawei community brief output contains communities but omits AS paths. Huawei AS-path brief output contains AS paths but omits communities. Tests preserve these omissions. BGP `valid` is not an RPKI validation result.
- `frr-live/`: complete lab FRR responses from `vtysh -c 'show bgp ipv4 unicast 1.1.1.0/24 json'`, `vtysh -c 'show bgp ipv6 unicast 2606:4700::/44 json'`, and `traceroute -n -w 1 -q 1 -s 10.250.1.1 1.1.1.1`.
- `arista_live_route.json`: complete cEOS 4.36.3M response from `show ip bgp 1.1.1.1 | json`. The live-provider replay uses this capture with the matching FRR and Huawei captures.
- `mikrotik-live/`: complete RouterOS 7.16.2 raw responses extracted from the lab JSONL query log. Each fixture retains its original timestamp, device, and query. The traceroute fixture includes all intermediate screen updates; the test runs the normal cleanup plugin before parsing.
- `frr_route_empty.json`, `frr_route_local.json`, `frr_route_inaccessible_nexthop.json`: complete FRRouting 10.2.2 responses from `vtysh -c 'show bgp ipv4 unicast <target> json'`. Targets are `100.64.0.0/10` (not in the table), `192.0.2.1` (locally sourced by a temporary `network 192.0.2.0/24` with a blackhole route) and `198.18.10.1` (injected from the core with unreachable next hop `10.99.99.99`). Both lab changes were reverted after capture. Issue #39.
- `arista_large_community.json`: complete cEOS 4.36.3M response from `show ip bgp 198.51.100.0/24 detail | json`. The core injected the route with `community 65000:100` and `large-community 65000:1:1`, then withdrew it after capture. Issue #38.
- `vyos-live/`: VyOS 1.5 stream responses from the lab router over SSH, using the FRR shell. `route4.json` and `route6.json` are complete responses from `vtysh -c 'show bgp ipv4 unicast 1.1.1.1 json'` and `vtysh -c 'show bgp ipv6 unicast 2606:4700::1111 json'`. `aspath4.json` (`regexp _37239_13335$`) and `community4.json` (`community 13335:10045`) keep the first five prefixes of 2,214 and 1,198 returned prefixes; route entries are unchanged. Issue #54.
- `openbgpd-live/`: OpenBGPD 8.8 responses from `bgpctl -j show rib detail <family> <filter>` on the lab router. `route4.json` (`inet 1.1.1.1`), `route6.json` (`inet6 2606:4700::1111`), `empty.json` (`inet 100.64.0.0/10`) and `large_community.json` (`inet 198.51.100.1`, injected from the core with `community 65000:100` and `large-community 65000:1:1`, then withdrawn) are complete. `aspath4.json` (`source-as 13335`) and `community4.json` (`community 37195:302`) keep the first five of 31,159 and 27,350 RIB entries; entries are unchanged. Issue #55.
