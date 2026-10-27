# Captured lab output

- `arista_aspath.json`: cEOS 4.36.3M, 27 October 2026, `show ip bgp regexp _13335$ | json`. Retains one complete route entry from 2,544 entries. No route fields are synthesized.
- `arista_traceroute.txt`: cEOS 4.36.3M, 27 October 2026, `traceroute ip 1.1.1.1 source 10.250.7.1`. Complete output, including MPLS annotations and multiple responders.
- `bird_traceroute.txt`, `openbgpd_traceroute.txt`, `vyos_traceroute.txt`: complete built-in traceroute responses from the corresponding lab devices, 27 October 2026, target `1.1.1.1`. Each capture includes all nine hops and the destination.

Synthetic cases in tests are explicitly separate from these device captures. Issues #22, #23 and #25 track the remaining hardware and configuration matrix.
