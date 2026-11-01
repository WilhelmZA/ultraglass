# Firewall acceptance lab

Supply compatible FortiGate and PAN-OS container images through `FORTIGATE_IMAGE` and `PANOS_IMAGE`. Activate the vendor licences required for BGP. Live validation remains pending.

```sh
sudo env FORTIGATE_IMAGE=your-fortigate-tag PANOS_IMAGE=your-panos-tag containerlab deploy -t lab/ultraglass-firewalls.clab.yml
```

Install or activate the licences through the vendor procedure before configuring BGP. Confirm the data-interface mapping for each image; the first data interface is normally FortiGate `port2` and PAN-OS `ethernet1/1`. The GoBGP core uses AS 65000.

- FortiGate: management `192.168.248.11`, local AS 65016, data addresses `10.248.1.1/31` and `2001:db8:248:1::1/127`, peers `10.248.1.0` and `2001:db8:248:1::`.
- PAN-OS: management `192.168.248.12`, local AS 65017, data addresses `10.248.2.1/31` and `2001:db8:248:2::1/127`, peers `10.248.2.0` and `2001:db8:248:2::`. Use the classic routing engine and virtual router `default`.

Activate the corresponding unicast address families and permit BGP and diagnostic traffic on the test data links.

```sh
docker exec clab-ultraglass-firewalls-core gobgp neighbor
docker exec clab-ultraglass-firewalls-core gobgp global rib add -a ipv4 198.51.100.1/32 nexthop 0.0.0.0 aspath "64999 13335" community 65000:777
docker exec clab-ultraglass-firewalls-core gobgp global rib add -a ipv6 2001:db8:100::1/128 nexthop :: aspath "64999 13335" community 65000:777
```

Configure `fortinet` and `paloalto_panos` devices with `attrs.source4` and `attrs.source6` set to their data-interface addresses. Test both route prefixes and diagnostics with structured output on and off. Capture `get system status` or `show system info` and the exact replies under `hyperglass/plugins/tests/fixtures/firewall-live/`. Repeat PAN-OS BGP queries with `vrf` set to a configured classic virtual-router name.

FortiGate uses the account's current VDOM. Restrict the account to the intended VDOM. Built-ins do not enter or create VDOMs, and explicit FortiGate VRF selection remains unimplemented. Verify diagnostic option isolation with two concurrent sessions, and test a rejected source option before accepting the diagnostic chain. The collector stops on a rejected FortiGate command and disconnects on errors or timeouts.

AS-path and community search commands, FortiGate explicit VRFs, PAN-OS VRF diagnostics and the PAN-OS advanced routing engine remain pending. Use verified custom directives for those cases. Reference BGP fixtures are published examples; IPv6 and traceroute unit samples are synthetic.

```sh
sudo env FORTIGATE_IMAGE=your-fortigate-tag PANOS_IMAGE=your-panos-tag containerlab destroy -t lab/ultraglass-firewalls.clab.yml
```
