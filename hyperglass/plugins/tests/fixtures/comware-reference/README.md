# Comware reference examples

These are normalized excerpts from published H3C Comware 7 command references, not lab captures. Whitespace is normalized and unused QoS fields are omitted.

- `route4.txt`: `display bgp routing-table ipv4 10.2.1.0 24`, from [BGP commands, R6749](https://www.h3c.com/en/d_202304/1830412_294551_0.htm).
- `route6.txt`: `display bgp routing-table ipv6 2:: 64`, from the same BGP reference.
- `trace6.txt`: `tracert ipv6 -vpn-instance vpn1 -resolve-as vpn 2001:3::2`, from [System maintenance and debugging commands](http://wwwsg.h3c.com/en/d_202208/1656972_294551_0.htm).

VSR1000 live captures remain pending. The documented Comware 7 BGP command uses configured `as-path-acl` and `community-list` identifiers rather than arbitrary user-supplied expressions or community values. Those query types are not advertised as built-ins.
