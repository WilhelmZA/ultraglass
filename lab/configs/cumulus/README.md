# Cumulus VX acceptance lab

This optional topology connects Cumulus VX to a dedicated GoBGP core in the default VRF and `LAB`. It uses a small deterministic table. Cumulus VX 5.4.0 live validation passes for both address families and routing contexts, in text and structured modes. Captures and regression tests are under `hyperglass/plugins/tests/fixtures/cumulus-live/` and `test_cumulus_live.py`.

## Validated behavior

Validation covers Cumulus VX 5.4.0 with FRR `7.5+cl5.3.0u0`. The capture manifest records the commands and software versions.

SSH enters the management VRF. Separate BGP peers supply distinct IPv4 and IPv6 prefixes to the default and LAB VRFs. Validation uses native interface and FRR configuration rather than the NVUE 5.16 example below.

All 32 onboarding cases and 32 independent uncached HTTP API comparisons pass. Checks include prefixes, AS paths, standard/large communities, next hops, best-path state, reported VRFs and traceroute addresses. Ping receives all five replies. Route fixtures differ between VRFs to detect routing-context leakage. Diagnostics target each VRF's own data-interface addresses. These checks do not establish remote forwarding behavior.

The validated SSH configuration uses explicit pacing. Without it, some reads return a prompt before command output. Both output modes use:

```yaml
driver_config:
  fast_cli: false
  global_delay_factor: 1
```

Live community queries exposed the FRR 7.5 prefix metadata header fixed in #217. Regression tests cover that response format. Results apply to VX 5.4.0; the NVUE 5.16 configuration example has not been live-tested.

## Start

Run hardware-dependent appliances inside an isolated lab VM without host device passthrough or host filesystem sharing.

Supply a compatible Cumulus VX container image through `CUMULUS_IMAGE`. The topology defaults to `vrnetlab/nvidia_cumulus-vx:5.16.1`. The BGP peer image comes from `lab/images/core`.

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

The command-construction tests retain their labelled FRR captures. The separate `test_cumulus_live.py` suite replays the captured VX 5.4 output and checks default/LAB routing contexts, both address families, text preservation and malformed-path rejection.

## Stop

```sh
sudo containerlab destroy -t lab/ultraglass-cumulus.clab.yml
```
