# Cumulus VX acceptance lab

This optional topology connects Cumulus VX to a dedicated GoBGP core in the default VRF and `LAB`. It uses a small deterministic table. Native command and shared-parser tests pass without this image. Live Cumulus captures and boot validation remain pending because no Cumulus VX image is available in the development lab.

## Start

Supply a Cumulus VX disk through the [vrnetlab Cumulus wrapper](https://github.com/srl-labs/vrnetlab/tree/master/nvidia/cumulus-vx). The topology defaults to its documented `vrnetlab/nvidia_cumulus-vx:5.16.1` tag. Set `CUMULUS_IMAGE` for another locally built tag. The core image comes from `lab/images/core`.

From the repository root:

```sh
sudo containerlab deploy -t lab/ultraglass-cumulus.clab.yml
scp lab/configs/cumulus/configure.sh cumulus@192.168.251.12:/tmp/configure-ultraglass.sh
ssh cumulus@192.168.251.12 'sh /tmp/configure-ultraglass.sh'
docker exec clab-ultraglass-cumulus-core gobgp neighbor
docker exec clab-ultraglass-cumulus-core gobgp global rib add -a ipv4 198.51.100.1/32 nexthop 0.0.0.0 aspath "64999 13335" community 65000:777
docker exec clab-ultraglass-cumulus-core gobgp global rib add -a ipv6 2001:db8:100::1/128 nexthop :: aspath "64999 13335" community 65000:777
```

The wrapper's documented lab credential is `cumulus` / `Clab123!`. Confirm all four BGP sessions reach `Establ` before testing. Copy the entries in `devices.yaml` into the test installation's devices file. Its network must reach `192.168.251.12`. Repeat with `structured_output: false` to compare text output.

## Capture acceptance evidence

Test both locations with route/ping/traceroute targets `198.51.100.1` and `2001:db8:100::1`, AS path `_64999_`, and community `65000:777`. Check that the VRF location returns `LAB` in structured BGP output. Verify both diagnostic targets respond from each VRF.

Capture the exact command replies over SSH, including the installed version from `cat /etc/os-release`. Store sanitized replies under `hyperglass/plugins/tests/fixtures/cumulus-live/` with the command and version metadata. The following commands illustrate IPv4 capture; repeat with IPv6 and the `vrf LAB` BGP form.

```sh
ssh cumulus@192.168.251.12 "sudo -n vtysh -c 'show bgp ipv4 unicast 198.51.100.1/32 json'" > route4.json
ssh cumulus@192.168.251.12 "sudo -n vtysh -c 'show bgp ipv4 unicast regexp _64999_ json'" > aspath4.json
ssh cumulus@192.168.251.12 "sudo -n vtysh -c 'show bgp ipv4 unicast community 65000:777 json detail'" > community4.json
ssh cumulus@192.168.251.12 'sudo -n ip vrf exec default traceroute -4 -n -q 1 -w 1 -s 10.252.1.1 198.51.100.1' > trace4.txt
```

Existing automated Cumulus tests explicitly reuse FRR captures. They establish command construction and shared-parser dispatch, not Cumulus VX live validation.

## Stop

```sh
sudo containerlab destroy -t lab/ultraglass-cumulus.clab.yml
```
