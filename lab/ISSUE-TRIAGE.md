# Open-issue triage — 27 October 2026

The review covers all 16 open issues. Severity reflects command execution, data correctness, query availability, validation gaps, then maintenance. Completed code changes await PR review and merge. Hardware validation items remain open.

| Order | Severity | Issue | Result |
| --- | --- | --- | --- |
| 1 | Critical | [#28](https://github.com/WilhelmZA/ultraglass/issues/28) command injection | Fixed in `1ea8099c`. Reject command syntax and quote complete Linux arguments. Twelve live rejection checks pass across six vendors. |
| 2 | High | [#19](https://github.com/WilhelmZA/ultraglass/issues/19) truncated output | Fixed in `6d0c3bb5`. Prompt reads preserve both lines across a three-second silent gap on the FRR lab SSH connection. MikroTik BGP also uses prompt reads. |
| 3 | High | [#30](https://github.com/WilhelmZA/ultraglass/issues/30) errors reported as success | Fixed in `6d0c3bb5`. Device errors produce warnings before parsing. An OpenBGPD rejection returned HTTP 400 during live validation. |
| 4 | Medium | [#34](https://github.com/WilhelmZA/ultraglass/issues/34) BIRD AS paths | Fixed in `1ea8099c`. `_13335$` returns matching routes using a path mask. Unsupported expressions fail validation. |
| 5 | Medium | [#31](https://github.com/WilhelmZA/ultraglass/issues/31) RouterOS 7 queries | Fixed in `1ea8099c` and `6d0c3bb5`. AS-path and community queries return 5,463 and 27,358 routes. Full-table scans take 92–159 seconds with a 300-second lab timeout. They are not sub-second operations. |
| 6 | Medium | [#32](https://github.com/WilhelmZA/ultraglass/issues/32) EOS JSON | Fixed in `9fb1d550`. Missing `routeDetail` caused validation failure. Live AS-path and community queries return 5,463 and 27,358 routes. Multiple JSON documents already work. |
| 7 | Medium | [#33](https://github.com/WilhelmZA/ultraglass/issues/33) EOS ping | Fixed in `6d0c3bb5`. Enable mode permits ping from the configured source. Live ping succeeds. |
| 8 | Medium | [#21](https://github.com/WilhelmZA/ultraglass/issues/21) FRR ICMP privilege | Fixed in `46b55967`. UDP traceroute runs as the unprivileged lab user and returns nine hops. |
| 9 | Medium | [#20](https://github.com/WilhelmZA/ultraglass/issues/20) Huawei defaults | Partial in `66b6b9da`. Documented defaults and enabled explicit VRPv8 support. Huawei hardware captures and both output modes still require validation. |
| 10 | Validation | [#22](https://github.com/WilhelmZA/ultraglass/issues/22) shared BGP model | Partial in `58bdb9a3`. Thirty-two policy and enrichment-dispatch tests cover four vendor parsers with mocked external services. Live Junos and Huawei validation remains open. The available vJunos image fails at KVM startup on this host. |
| 11 | Validation | [#23](https://github.com/WilhelmZA/ultraglass/issues/23) mixed-vendor selection | Partial. Cross-vendor API requests run against six vendors with mixed output settings. Fixed OpenBGPD AS-selector incompatibility in `1ea8099c`. The browser selection flow and unavailable vendor matrix remain open. |
| 12 | Validation | [#25](https://github.com/WilhelmZA/ultraglass/issues/25) captured fixtures | Partial in `9fb1d550` and `66b6b9da`. Added captured EOS BGP and EOS, BIRD, OpenBGPD, and VyOS traceroute fixtures. Remaining platforms and query types still need captures. |
| 13 | Low | [#26](https://github.com/WilhelmZA/ultraglass/issues/26) Redis tests | Fixed in `53f5a5a4`. Every backend test uses an isolated in-memory Redis store. No local Redis service is required. |
| 14 | Low | [#35](https://github.com/WilhelmZA/ultraglass/issues/35) traceroute coverage | Partial in `66b6b9da`. Added a standard CLI parser and preserved raw-output fallback. Captured EOS and Linux traces pass. Other hardware formats remain open. |
| 15 | Low | [#27](https://github.com/WilhelmZA/ultraglass/issues/27) UTC timestamps | Fixed in `9fb1d550`. EOS, FRR, and query timestamps use timezone-aware UTC. EOS defaults evaluate per route. |
| 16 | Low | [#24](https://github.com/WilhelmZA/ultraglass/issues/24) unused enrichment selectors | Fixed in `e609f3c2`. Common plugins declare no misleading platform or directive selectors. |

## Verification

- Backend: 250 tests pass without a local Redis server.
- Python wheel and source distribution builds pass.
- Docker build passes for `ultraglass-lab/ultraglass:issue-fixes`.
- Forty-eight API status and input-rejection checks pass across EOS, FRR, BIRD, OpenBGPD, MikroTik, and VyOS after corrections. These checks do not replace full plain-text result or browser validation.
- Additional live traceroute checks confirm structured output for opted-in BIRD and VyOS, and text output for non-opted-in OpenBGPD.
- `lab/scripts/verify-issues.py` retains full API evidence. Parser fixtures identify capture provenance in `hyperglass/plugins/tests/fixtures/README.md`.

## Remaining acceptance evidence

- Huawei VRP and VRPv8: real BGP and traceroute captures, with structured output enabled and disabled.
- Junos: a working virtualization host, then live shared-model validation.
- Cisco IOS, IOS-XR, NX-OS, Nokia SR OS, and TNSR: real output and parser validation.
- Mixed-vendor browser selection: each query type, including mixed structured and text devices.
- Shared-model live matrix: community modes, both external RPKI backends, and inline versus asynchronous enrichment. Unit tests mock external services and do not prove provider availability or browser rendering.
