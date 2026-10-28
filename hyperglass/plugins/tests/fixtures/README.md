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
