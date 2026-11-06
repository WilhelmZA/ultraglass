# ArcOS OpenConfig reference

These JSON documents follow the ConfD show path documented for Arrcus ArcOS:

`show network-instance <vrf> protocol BGP BGP | display json`

They reconstruct OpenConfig BGP loc-rib leaves that the netlab ArcOS validator walks (`prefix`, `next-hop`, `as-path` `AS_SEQ` members, `community`, `valid-route`, neighbor `session-state`). They are not live device captures.

- `route4.json`: IPv4 loc-rib path `10.0.0.0/16` plus an IPv6 loc-rib path and a neighbor session object that must not parse as a route.
- `route4-attrset.json`: the same IPv4 path with attributes referenced through `attr-index`.
- `route4-multipath.json`: two IPv4 loc-rib paths for `10.0.0.0/16`, including an ASDOT segment. This case is synthetic.

Capture authentic ConfD JSON from an ArcOS device before claiming live acceptance. Ping, traceroute, AS-path and community searches are omitted until those commands are confirmed on a device.
