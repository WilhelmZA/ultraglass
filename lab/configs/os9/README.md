# Dell acceptance lab

`ultraglass-dell.clab.yml` runs the existing OS9 image with an isolated GoBGP core at `192.168.249.10` and OS9 at `192.168.249.12`. It reuses the existing data-link configuration and does not stop other optional appliances.

```sh
sudo containerlab deploy -t lab/ultraglass-dell.clab.yml
docker exec clab-ultraglass-dell-core gobgp global rib add 1.1.1.0/24 nexthop 10.251.9.2 aspath 13335 community 37195:302
docker exec clab-ultraglass-dell-core gobgp global rib add -a ipv6 2606:4700::/44 nexthop fd00:251:9::2 aspath 13335 community 37195:302
```

After OS9 boots, log in with the lab credential `admin` / `Lab-Router9` and enable the configured peers:

```text
configure terminal
router bgp 65029
 no neighbor 10.251.9.2 shutdown
 no neighbor fd00:251:9::2 shutdown
end
```

Test both prefixes, AS path `_13335$`, community `37195:302`, and diagnostics to `1.1.1.1` and `2606:4700::1111`. Use a `dell_force10` device with structured output on and off. Capture `show version` and exact command output under `hyperglass/plugins/tests/fixtures/dell-live/`. Repeat BGP and ping in a named VRF. OS9 traceroute VRFs are E-Series-specific and are not advertised.

The OS10 virtual edition is not supplied. Attach an operator-provided OS10 appliance to a GoBGP data link for separate acceptance. Configure it as `dell_os10`, set diagnostic source addresses, and repeat the route, community and diagnostic tests in default and named VRFs. Arbitrary AS-path regex search is unsupported on OS10; configured filter lists need custom directives.

Reference fixtures in `dell-reference` are published examples. The local OS9 9.13.0.0 image reaches `SYSTEM_READY` on the AMD host, but its wrapper does not become healthy within the 180-second acceptance wait. No SSH queries or live captures pass this attempt. Live default/VRF captures remain required for full acceptance. OS10's documented detailed BGP output differs from FRR JSON, so the implementation uses its native CLI.

```sh
sudo containerlab destroy -t lab/ultraglass-dell.clab.yml
```
