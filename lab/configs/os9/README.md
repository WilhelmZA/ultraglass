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
 neighbor 10.251.9.2 no shutdown
 neighbor fd00:251:9::2 no shutdown
end
```

Test both prefixes, IPv4 AS path `_13335$`, community `37195:302`, and diagnostics to `1.1.1.1` and `2606:4700::1111`. Use a `dell_force10` device with structured output on and off. Authentic OS9 9.13 captures are under `hyperglass/plugins/tests/fixtures/dell-os9-live/`. Repeat BGP and ping in a named VRF. OS9 traceroute VRFs are E-Series-specific and are not advertised.

The OS10 virtual edition is not supplied. Attach an operator-provided OS10 appliance to a GoBGP data link for separate acceptance. Configure it as `dell_os10`, set diagnostic source addresses, and repeat the route, community and diagnostic tests in default and named VRFs. Arbitrary AS-path regex search is unsupported on OS10; configured filter lists need custom directives.

## OS9 link readiness

OS9 9.13(0.0) requires `no keepalive` on `managementethernet 0/0` and each emulated data interface. Without it, interfaces remain administratively up with line protocol down. The bootstrap and `startup.cfg` now apply this setting. Rebuild the OS9 image to update its management bootstrap; apply the setting through the console on an existing appliance.

Live checks confirm that enabling keepalive drops both interfaces and causes data-link pings to fail. Disabling keepalive restores both interfaces. SSH authentication and management IPv4, data IPv4 and data IPv6 pings then pass. `Pluggable media not present` still appears while the interfaces pass traffic; it does not prove a link failure.

The SSH server can initially report disabled after `ip ssh server enable`. Wait for `show ip ssh` to report enabled and verify an authenticated SSH command. Allow IPv6 neighbor discovery to settle after changing link state.

## Verified OS9 9.13 query matrix

The live run passes 28 onboarding CLI queries, 28 independent uncached HTTP API comparisons and 28 browser queries. Default VRF has eight cases per output mode: two prefix queries, one IPv4 AS-path query, one dual-stack community query, two pings and two traceroutes. `LAB` has six cases per mode because VRF traceroute is not offered. Structured mode returns route and traceroute tables; AS-path/community summaries and ping remain text. Text mode preserves native output. Browser checks verify the rendered tables, community menus and text results.

Two BGP sessions carry distinct IPv4/IPv6 routes into default and `LAB`. Queries for the other VRF's prefixes return no routes in all four negative controls. `feature vrf` must precede `ip vrf LAB`. Declare the LAB neighbor in `address-family ipv4 vrf LAB`, then activate it in `address-family ipv6 unicast vrf LAB` for both families over one IPv4 BGP session.

The accepted command forms include `ping vrf LAB TARGET count 5` and `show ip bgp vrf LAB regexp PATTERN`. The latter returns IPv4 routes only. Explicit AFI selectors before `regexp` are rejected. Detailed route output contains `Metric 4294967295 (Default)` and community values below `Communities :`; the parser preserves the printed metric and reads those community values.

The test appliance uses `ip ssh connection-rate-limit 60` for automated queries. The default limit of ten connections per minute caused SSH banner failures. Its application device entries use these SSH settings:

```yaml
driver_config:
  fast_cli: false
  global_delay_factor: 1
  conn_timeout: 30
  banner_timeout: 60
  auth_timeout: 60
```

Direct ping captures reach the data-link gateways in each VRF with 5/5 replies. Application diagnostics target each VRF's own data-interface addresses. Default-VRF traceroutes reach that address in one hop; this validates native command execution and rendering, not remote routed traceroute forwarding.

The `dell-os9-live` manifest records all 22 capture commands. Reference fixtures in `dell-reference` remain labelled published examples. OS10 still needs separate live acceptance under #74.

```sh
sudo containerlab destroy -t lab/ultraglass-dell.clab.yml
```
