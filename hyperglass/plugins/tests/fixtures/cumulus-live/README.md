# Cumulus VX 5.4 live captures

Captured over SSH on 2026-11-01 from the vendor Cumulus VX 5.4.0 QEMU image. `version.txt` and `frr-version.txt` record Cumulus 5.4.0 and FRR `7.5+cl5.3.0u0`. Sanitization replaces the GoBGP host name with `gobgp-fixture` and removes trailing whitespace from JSON closing lines. These files contain actual appliance output.

`manifest.json` records the exact command for each capture. `default-*` queries the default VRF; `lab-*` queries `LAB`. JSON files contain structured BGP commands. Matching text files contain the native text commands. Both address families include route, AS-path, community, ping and traceroute captures. `ssh-vrf.txt` confirms that the SSH shell starts in `mgmt`.

| Context | IPv4 prefix | IPv6 prefix | AS path | Next hops |
|---|---|---|---|---|
| default | `1.0.0.0/24` | `2606:4700:4700::/48` | `64999 13335` | `10.252.1.2`, `2001:db8:252:1::2` |
| LAB | `198.51.100.0/24` | `2001:db8:100::/48` | `64999 64497` | `10.252.2.2`, `2001:db8:252:2::2` |

All routes carry community `65000:777` and large community `65000:777:1`. Route and community detail responses expose both. AS-path summary responses omit communities. `bgp-summary.json` records established neighbors and one received prefix per address family in each VRF.

The community JSON uses a list whose first object contains `prefix` and `advertisedTo`. That object describes the prefix, not a path. The following objects contain the actual paths. This schema caused #217 before the parser fix.

Diagnostics target each VRF's own interface address (`10.252.N.1` and `2001:db8:252:N::1`). They confirm native command execution, source binding and explicit VRF selection from a management-VRF SSH session. Traceroute reaches that local address in one hop. The restricted user-mode network does not supply a remote UDP traceroute responder.

Application validation uses `driver_config: {fast_cli: false, global_delay_factor: 1}`. All 32 CLI cases and 32 uncached HTTP API comparisons pass on the patched source.
