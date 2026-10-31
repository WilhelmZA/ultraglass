# OcNOS acceptance lab

Build a licensed OcNOS 6.5+ image using [vrnetlab's OcNOS wrapper](https://github.com/srl-labs/vrnetlab/tree/master/ipinfusion/ocnos). Supply its local tag through `OCNOS_IMAGE`. The topology uses a separate management network and the existing `ultraglass-lab/core:latest` GoBGP image. Boot on the AMD lab host and live capture remain pending because no OcNOS image is available.

From the repository root:

```sh
sudo env OCNOS_IMAGE=your-local-ocnos-image containerlab deploy -t lab/ultraglass-ocnos.clab.yml
```

Enable SSH on `192.168.253.12` if the supplied image enables only Telnet. Confirm the interface mapped to `eth1`. Assign `10.254.1.1/31` and `2001:db8:254:1::1/127` to it. Configure BGP AS 65014 and peers `10.254.1.0` and `2001:db8:254:1::`, both in AS 65000. Activate the IPv4 and IPv6 unicast address families respectively.

```sh
docker exec clab-ultraglass-ocnos-core gobgp neighbor
docker exec clab-ultraglass-ocnos-core gobgp global rib add -a ipv4 198.51.100.1/32 nexthop 0.0.0.0 aspath "64999 13335" community 65000:777
docker exec clab-ultraglass-ocnos-core gobgp global rib add -a ipv6 2001:db8:100::1/128 nexthop :: aspath "64999 13335" community 65000:777
```

Configure an `ipinfusion_ocnos` device at `192.168.253.12` in the test installation. Set `driver_config.secret` if privileged mode needs a password. Query both prefixes, AS path `_13335$`, IPv4 community `65000:777`, ping and traceroute with structured output on and off. Preserve `show version` and the exact replies under `hyperglass/plugins/tests/fixtures/ocnos-live/`. Repeat diagnostics in a named VRF after configuring its interfaces and routes.

Published reference excerpts in `ocnos-reference` are not live captures. BGP queries on named VRFs, IPv6 community filtering and structured summary parsing remain pending. The built-ins omit those forms rather than infer unsupported syntax.

```sh
sudo env OCNOS_IMAGE=your-local-ocnos-image containerlab destroy -t lab/ultraglass-ocnos.clab.yml
```
