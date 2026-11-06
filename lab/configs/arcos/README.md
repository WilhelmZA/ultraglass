# ArcOS acceptance lab

Supply a locally tagged ArcOS container image through `ARCOS_IMAGE`. ArcOS is a native containerlab kind (`arrcus_arcos`). The topology uses `ultraglass-lab/core:latest` for its BGP peer. Live validation remains pending.

```sh
sudo env ARCOS_IMAGE=arcos:8.2.1A.P2 containerlab deploy -t lab/ultraglass-arcos.clab.yml
```

Connect to `192.168.247.12`. Confirm the data interface mapped to `swp1`; assign `10.247.1.1/31` and `2001:db8:247:1::1/127` to it. Configure BGP AS 65016 with IPv4 peer `10.247.1.0` and IPv6 peer `2001:db8:247:1::`, both in AS 65000. Use protocol instance name `BGP` in network-instance `default`.

The tested container image enables SSH only after the factory-default admin password is changed and `ssh-server` is enabled. Queries expect a Linux shell that can run `confd_cli`.

```sh
docker exec clab-ultraglass-arcos-core gobgp neighbor
docker exec clab-ultraglass-arcos-core gobgp global rib add -a ipv4 198.51.100.1/32 nexthop 0.0.0.0 aspath "64999 13335" community 65000:777
docker exec clab-ultraglass-arcos-core gobgp global rib add -a ipv6 2001:db8:100::1/128 nexthop :: aspath "64999 13335" community 65000:777
```

Configure an `arrcus_arcos` device at `192.168.247.12` in the test installation. Test both prefixes with structured output on and off:

```text
echo 'show network-instance default protocol BGP BGP | display json' | confd_cli -C -u admin
```

Capture `show version` and the exact ConfD JSON under `hyperglass/plugins/tests/fixtures/arcos-live/`. Repeat after configuring a named network-instance and its BGP instance.

The `arcos-reference` fixtures reconstruct OpenConfig loc-rib JSON from that show path. They are not device captures. Ping, traceroute, AS-path and community searches are not exposed. Do not use the `arrcus.arcos` Ansible `network_cli` transport against this image; it hangs on `config terminal`.

```sh
sudo env ARCOS_IMAGE=arcos:8.2.1A.P2 containerlab destroy -t lab/ultraglass-arcos.clab.yml
```
