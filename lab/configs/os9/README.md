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

## OS9 link readiness

OS9 9.13(0.0) requires `no keepalive` on `managementethernet 0/0` and each emulated data interface. Without it, interfaces remain administratively up with line protocol down. The bootstrap and `startup.cfg` now apply this setting. Rebuild the OS9 image to update its management bootstrap; apply the setting through the console on an existing appliance.

Live checks confirm that enabling keepalive drops both interfaces and causes data-link pings to fail. Disabling keepalive restores both interfaces. SSH authentication and management IPv4, data IPv4 and data IPv6 pings then pass. `Pluggable media not present` still appears while the interfaces pass traffic; it does not prove a link failure.

The SSH server can initially report disabled after `ip ssh server enable`. Wait for `show ip ssh` to report enabled and verify an authenticated SSH command. Allow IPv6 neighbor discovery to settle after changing link state.

Reference fixtures in `dell-reference` are published examples. Full default/VRF query validation and authentic parser fixtures remain required for #74. OS10 needs separate live acceptance.

```sh
sudo containerlab destroy -t lab/ultraglass-dell.clab.yml
```
