# AOS-CX acceptance lab

Supply a compatible AOS-CX 10.14 container image through `AOSCX_IMAGE`. The topology uses `ultraglass-lab/core:latest` for its BGP peer. Live validation remains pending.

```sh
sudo env AOSCX_IMAGE=your-local-aoscx-image containerlab deploy -t lab/ultraglass-aoscx.clab.yml
```

Connect to `192.168.254.12`. Confirm the data interface mapped to `eth1`; assign `10.255.1.1/31` and `2001:db8:255:1::1/127` to it. Configure BGP AS 65015 with IPv4 peer `10.255.1.0` and IPv6 peer `2001:db8:255:1::`, both in AS 65000. Activate the corresponding unicast address families.

```sh
docker exec clab-ultraglass-aoscx-core gobgp neighbor
docker exec clab-ultraglass-aoscx-core gobgp global rib add -a ipv4 198.51.100.1/32 nexthop 0.0.0.0 aspath "64999 13335" community 65000:777
docker exec clab-ultraglass-aoscx-core gobgp global rib add -a ipv6 2001:db8:100::1/128 nexthop :: aspath "64999 13335" community 65000:777
```

Configure an `aruba_aoscx` device at `192.168.254.12` in the test installation. Set `attrs.source4` and `attrs.source6` to the data-interface addresses. Test both prefixes, community `65000:777`, ping and traceroute with structured output on and off. Capture `show version` and exact command replies under `hyperglass/plugins/tests/fixtures/aoscx-live/`. Repeat route and diagnostic queries after configuring a named VRF and its BGP peers.

The `aoscx-reference` fixtures are published CLI examples, not device captures. AS-path search and dual-stack community VRF syntax remain unverified and are not exposed. Community summaries remain text. Validate IPv6 and multipath details before claiming full live acceptance.

REST was considered: [the vendor introduction](https://developer.arubanetworks.com/aoscx/docs/introduction) requires login/logout with cookies and a CSRF token on 10.09+. CLI integration reuses the current SSH credential and transport model. A native REST integration needs a session lifecycle and captured operational BGP payloads.

```sh
sudo env AOSCX_IMAGE=your-local-aoscx-image containerlab destroy -t lab/ultraglass-aoscx.clab.yml
```
