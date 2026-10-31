# OcNOS reference examples

These are transcribed vendor examples, not live lab captures. Whitespace is normalized.

- `route4.txt`: `show bgp ipv4 unicast 22.22.22.22/32`, from the [OcNOS 6.5 BGP reference](https://docs.ipinfusion.com/ocnos-data-centers-6.5/OcNOS_DC/BGP-CR/BGP-show-cmds.html).
- `route6.txt`: `show bgp ipv6 6666::/64`, from the same reference. The separate `valid, sourced, best` line must set the best-path flag.
- `trace4.txt`: `traceroute ip 10.10.100.126 vrf management`, from [Basic Commands](https://docs.ipinfusion.com/ocnos-data-centers-6.5/OcNOS_DC/General_Sysman_Cmds/Common_IMI_Commands.html).

Live OcNOS captures remain pending. AS-path and community summary formats stay text until captured layouts can be validated.
