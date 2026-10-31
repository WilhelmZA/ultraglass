# Comware 7 acceptance lab

Build a licensed VSR1000 image using [vrnetlab's HPE wrapper](https://github.com/srl-labs/vrnetlab/tree/master/hp/vsr1000). Supply its local image tag through `COMWARE_IMAGE`. The isolated topology uses the existing `ultraglass-lab/core:latest` image and two BGP sessions. VSR1000 boot and live captures remain pending because the development lab has no image.

From the repository root:

```sh
sudo env COMWARE_IMAGE=your-local-vsr1000-image containerlab deploy -t lab/ultraglass-comware.clab.yml
```

Log in to `192.168.252.12` with the configured lab credential `vrnetlab` / `VR-netlab9`. Configure the data interface mapped to `eth1` with `10.253.1.1/31` and `2001:db8:253:1::1/127`. Configure BGP AS 65013 with IPv4 peer `10.253.1.0` and IPv6 peer `2001:db8:253:1::`, both in AS 65000. Enable the corresponding unicast address family for each peer. Confirm the interface mapping on the supplied image before applying configuration.

```sh
docker exec clab-ultraglass-comware-core gobgp neighbor
docker exec clab-ultraglass-comware-core gobgp global rib add -a ipv4 198.51.100.1/32 nexthop 0.0.0.0 aspath "64999 13335" community 65000:777
docker exec clab-ultraglass-comware-core gobgp global rib add -a ipv6 2001:db8:100::1/128 nexthop :: aspath "64999 13335" community 65000:777
```

Add a `hp_comware` device at `192.168.252.12` to the test installation. Set `source4` and `source6` to the data-interface addresses. Test route, ping, and traceroute against both injected addresses with structured output on and off. Capture `display version` and the exact command replies under `hyperglass/plugins/tests/fixtures/comware-live/`. Repeat after placing the data interface and BGP peers in VPN instance `LAB` and setting `vrf: LAB` on the device.

The current tests use published command-reference excerpts under `comware-reference`; they are not live VSR1000 evidence. AS-path and community queries need configured router lists and custom directives.

```sh
sudo env COMWARE_IMAGE=your-local-vsr1000-image containerlab destroy -t lab/ultraglass-comware.clab.yml
```
