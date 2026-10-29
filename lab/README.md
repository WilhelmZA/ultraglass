# Ultraglass multi-vendor lab

A containerlab topology for testing ultraglass against every supported platform, with a real full BGP table. A GoBGP core sends the table (RIPE RIS rrc19, NAPAfrica Johannesburg) to each device under test over eBGP. Ultraglass queries each device over the management network.

## Requirements

- Docker, and containerlab 0.82 or newer (`containerlab version`)
- Passwordless sudo for `containerlab deploy`
- About 8 GB RAM for the Linux devices; more per added VM-based vendor

## Layout

- `ultraglass-lab.clab.yml` — the topology
- `images/` — Dockerfiles: `core` (GoBGP), `frr`, `bird`, `openbgpd`
- `configs/` — per-device config, plus `ultraglass/` (config.yaml, devices.yaml)
- `scripts/` — `build-images.sh`, `fetch-table.sh`, `inject-table.sh`, `silent-hop.sh`, `smoke-test.py`
- `data/` — the downloaded table dump (git-ignored)

## First-time setup

```sh
./scripts/build-images.sh          # core, frr, bird, openbgpd, ultraglass:dev
./scripts/fetch-table.sh           # download rrc19 full table into data/
```

MikroTik and Arista images are built separately (see their sections below). Build Juniper with `sh scripts/build-junos.sh <vjunos.qcow2>` and Cisco IOL with `sh scripts/build-cisco-iol.sh <refplat.iso>`.

## Start and stop

```sh
./lab-up.sh                        # whole lab (all vendors), injects the table
./lab-up.sh frr                    # ONE device only: core + redis + ultraglass + frr
./lab-up.sh --image wilhelmza/ultraglass:3.4.0-rc.2   # run a published image instead of the dev build
./lab-down.sh                      # stop and remove everything (built images are kept)
./lab-status.sh                    # containers + BGP session state
```

`lab-up.sh` is safe to run after a reboot. GoBGP keeps the table in memory, so it is injected fresh on every start. The single-device form (`./lab-up.sh <name>`, one of frr, bird, openbgpd, mikrotik, arista, vyos, huawei, junos, iol, ioll2) starts only that device plus the core, so it runs on far less RAM than the full lab. Use it on a stopped lab; Containerlab rejects a node filter that excludes running nodes during reconciliation.

`--image <reference>` must come first, before an optional device name. Without it, both Ultraglass instances run the local dev build `ultraglass-lab/ultraglass:dev`. `lab-up.sh` pulls the image when it is not present. It then compares the image ID with each running Ultraglass container and removes any container that runs a different image, so the deploy recreates it. This also applies after you rebuild the dev image. `docker restart` and a plain redeploy keep a container's old image.

Low-RAM machines can also cap the table size:

```sh
PREFIXES=50000 ./lab-up.sh frr     # inject 50k prefixes per family instead of the full ~1.1M
```

### BGP session control

Keep BGP sessions disabled for routers that are not under test to reduce routing-table RAM use. Enable both IPv4 and IPv6 sessions when testing a router. Leave the core running to retain the injected table.

Use `disable` or `enable` on the core. Select the router numbers in the loop: FRR `1`, BIRD `2`, OpenBGPD `3`, MikroTik `4`, VyOS `5`, Junos `6`, Arista `7`, Huawei `8`, Cisco IOL `9`, Cisco IOL-L2 `10`.

```sh
# Disable unused routers while testing Cisco and Junos.
ACTION=disable                  # change to enable to restore selected sessions
for N in 1 2 3 4 5 7 8; do
    docker exec clab-ultraglass-core gobgp neighbor "10.250.$N.1" "$ACTION"
    docker exec clab-ultraglass-core gobgp neighbor "fd00:250:$N::1" "$ACTION"
done
./lab-status.sh
```

Disabled sessions show `Idle(Admin)`. Enabled sessions should reach `Establ`. These changes are runtime-only; repeat the selection after the core restarts. Current selection, set on 28 October 2026: Junos, Cisco IOL and Cisco IOL-L2 enabled; all other router sessions disabled.

Two Ultraglass instances run against the same devices so every query can be cross-checked. http://127.0.0.1:8001 (`configs/ultraglass/`) sets `structured_output: true` on every device, so each platform returns whatever structured parsers it has. http://127.0.0.1:8002 (`configs/ultraglass-text/`) sets `structured_output: false` on every device and has no `structured` block, so every query returns raw device text. Each instance uses its own Redis database (1 and 2), so neither can serve the other's cached result. BIRD, OpenBGPD and VyOS have structured traceroute only; their BGP queries return text on both instances.

Query a device by name: lab-frr, lab-bird, lab-openbgpd, lab-mikrotik, lab-arista, lab-vyos, lab-huawei, lab-junos, lab-iol, lab-ioll2. Run `./scripts/smoke-test.py lab-junos lab-iol lab-ioll2` to check the new nodes through the API.

Run `python3 scripts/verify-issues.py --api http://127.0.0.1:8001/api --output /path/to/evidence lab-arista lab-frr lab-bird lab-mikrotik` to check mixed-vendor directive resolution and rejected command-injection inputs. The script retains complete API responses in `results.json`. Keep `logging.samples.enable` enabled to capture device output. Run against an isolated test instance when comparing code versions so cached results cannot mask a regression.

Run `python3 scripts/verify-browser.py --url http://127.0.0.1:8001 --output /path/to/browser-evidence lab-huawei lab-arista lab-frr lab-bird lab-openbgpd lab-vyos` with Playwright and Chromium installed to test all five query types through mixed-vendor UI selection. The script includes MikroTik, opens each result panel, and checks rendered tables or text against the API response. It retains JSON evidence and viewport screenshots.

Run `python3 scripts/verify-policies.py --routinator https://routinator.nlnetlabs.nl --output /path/to/policy-results.json` with development dependencies installed to replay captured EOS, FRR, and Huawei routes against live RPKI and enrichment providers. The 36 cases cover community deny/permit/name modes, Cloudflare/Routinator, and inline/deferred enrichment. This replay checks model data; it does not replace browser or live-device query validation.

Set `ULTRAGLASS_LAB_API=http://127.0.0.1:8003/api` when running `pytest tests/` against an isolated API instance (8002 is the text instance). The default remains port 8001.

## Devices

| Node | Platform | Mgmt IP | Login | Notes |
|---|---|---|---|---|
| core | GoBGP | 192.168.250.10 | — | full table source, lab gateway |
| frr | frr | 192.168.250.11 | lg / lg | structured output |
| bird | bird | 192.168.250.12 | root / lg | birdc needs root socket |
| openbgpd | openbgpd | 192.168.250.13 | root / lg | bgpctl needs root socket |
| mikrotik | mikrotik_routeros | 192.168.250.14 | admin / admin | CHR 7.16.2, full table, eBGP to core |
| vyos | vyos | 192.168.250.15 | admin / admin | VyOS 1.5 stream, full table, SSH enabled in boot config |
| junos | juniper | 192.168.250.16 | admin / admin@123 | vJunos-router 26.2R1.7, vrnetlab AMD patch |
| arista | arista_eos | 192.168.250.17 | admin / admin | cEOS 4.36.3M, full table, structured output |
| huawei | huawei (VRP) | 192.168.250.18 | admin / admin | CE12800 V200R005 (vrnetlab qemu), capped table, structured output |
| iol | cisco_ios | 192.168.250.19 | admin / admin | IOS XE 17.18.2 router, vrnetlab IOL wrapper, 4 GB router memory |
| ioll2 | cisco_ios | 192.168.250.20 | admin / admin | IOS XE 17.18.2 switch, routed data port, 4 GB router memory |
| ultraglass | — | 192.168.250.2 | — | this repo's image, port 8001 |
| ultraglass-text | — | 192.168.250.4 | — | same image, all text, port 8002 |
| redis | — | 192.168.250.3 | — | cache only, no persistence |

Juniper and Cisco IOL run through vrnetlab wrappers. Nokia SR OS still needs its image and license.

### Juniper vJunos-router on AMD

The original build skipped an upstream AMD fix. The vendor disk checks for Intel `vmx` rather than AMD `svm`. [vrnetlab PR #459](https://github.com/srl-labs/vrnetlab/pull/459) patches that check, and current launchers use `-cpu host`. Local validation on 28 October 2026 confirms FPC `Online` and established IPv4/IPv6 BGP on this Ryzen host.

Run `sh scripts/build-junos.sh ~/Downloads/vJunos-router-26.2R1.7.qcow2`. The script preserves the vendor disk and builds `ultraglass-lab/juniper_vjunos-router:26.2R1.7` from a patched copy. Give the node at least one data link and verify `show chassis fpc` reports `Online`; SSH alone does not prove forwarding works.

The persistent `junos` node passes IPv4/IPv6 BGP route, IPv4 ping and traceroute queries on both Ultraglass instances. Structured route queries return 13 IPv4 paths and 11 IPv6 paths for the test prefixes. The broad AS13335 path query exceeds the smoke test's 120-second timeout; the full Junos smoke run does not pass.

### Cisco IOL router and switch wrappers

`scripts/build-cisco-iol.sh` extracts the IOL and IOL-L2 container archives from `refplat-20260409-free.iso` and builds them with the pinned upstream vrnetlab wrapper. Images are `ultraglass-lab/cisco_iol:17.18.02` and `ultraglass-lab/cisco_iol:L2-17.18.02`. Both use Containerlab kind `cisco_iol`; the switch also sets `type: l2`.

The only wrapper adjustment adds `-m "${IOL_MEMORY:-4096}"` to the IOL launch command. Both the default allocation and 2 GB fail with `No memory` during full-table import. The topology explicitly sets `IOL_MEMORY: "4096"`. Partial startup configs preserve Containerlab's SSH and management VRF setup, then configure Ethernet0/1 and dual-stack BGP.

IOL reads the partial startup config only on its first boot. `lab-up.sh` runs `scripts/save-cisco-iol.sh` to save it to NVRAM before a later restart. After a direct `containerlab deploy`, run `sh scripts/save-cisco-iol.sh` yourself. Core addressing for the Cisco links is applied by `lab-up.sh`.

Both Cisco nodes hold 1,094,726 IPv4 and 261,509 IPv6 prefixes. BGP route, AS-path, community, IPv4 ping and traceroute queries pass on both Ultraglass instances. Cisco BGP output is text; the structured instance parses traceroute hops.

For Cisco IPv6 BGP route queries, enter a prefix such as `2606:4700::/44`. IOS XE rejects a bare IPv6 address in this command.

The supplied free ISO contains IOS XE IOL images, not IOSv, XRd or NX-OS. Cisco's [CML image license terms](https://developer.cisco.com/docs/modeling-labs/cml-free/) apply independently of the wrapper.

[CML Free](https://developer.cisco.com/docs/modeling-labs/cml-free/) requires a free Cisco account and registration, with no subscription or time limit. It includes IOL XE routing, IOL L2 switching and ASAv, with five simultaneous nodes. [Register](https://mkto.cisco.com/cml-free.html), then [download CML Free](https://software.cisco.com/download/home/286193282/type/286326381/release/CML-Free).

An alternative deployment is a local CML VM connected through an [L2 external connector](https://developer.cisco.com/docs/modeling-labs/external-connectors/). This supports external BGP peers and inbound SSH from Ultraglass.

[CML Personal](https://u.cisco.com/labs/cisco-modeling-labs-personal-1) is advertised at US$199 and includes 20 nodes. Its [reference image collection](https://developer.cisco.com/docs/modeling-labs/reference-platforms-and-images/) adds IOSv, Catalyst 8000V, XRd, XRv9000 and Nexus 9300v. This provides a purchase path without an existing hardware support contract. [DevNet Sandbox](https://developer.cisco.com/sandbox) provides free remote Cisco lab access as another option.

### Nokia SR OS trial and lab access

For local deployment, request an SR-SIM evaluation image and license from Nokia or a Nokia IP networking partner. SR-SIM requires a license at boot. Nokia also explicitly documents [vSIM trial requests](https://documentation.nokia.com/sr/22-10/books/vsim-installation-setup/vsim-software-licens.html). An evaluation request still needs vendor approval; no anonymous local trial download was verified.

[My Nokia Learning Labs](https://www.nokia.com/networks/training/src/mysrlab/) advertises remote lab access from €100 for 30 hours. This is a remote training option; external SSH access and custom BGP peering for Ultraglass need confirmation before purchase. Public SR Linux images do not replace SR OS driver coverage.

### MikroTik CHR — build notes (three traps)

The CHR image is a vrnetlab build. Use **RouterOS 7.16.2, not 7.25**: 7.25 forces a full ANSI interactive console (it loops cursor-position and terminal-identify queries after login) that netmiko cannot drive, so every query fails with `ReadTimeout`. 7.16.2 is on vrnetlab's tested list and netmiko drives it cleanly. This is a CHR console regression, not an ultraglass bug — production RouterOS devices work.

```sh
git clone https://github.com/srl-labs/vrnetlab
# download chr-7.16.2.vmdk from mikrotik.com/download
# assemble a build context with routeros/docker/{Dockerfile,launch.py}, common/{healthcheck.py,vrnetlab.py} and the vmdk
# then: docker build --build-arg IMAGE=chr-7.16.2.vmdk --build-arg VERSION=7.16.2 -t vrnetlab/mikrotik_routeros:7.16.2 <ctx>
```

Patch `launch.py` before building:

1. `ram=256` → `ram=2048`. 256 MB cannot hold a full table.
2. Add `b"CHR Login"` to the login `expect()` list (and an `elif ridx == 2:` branch that sends `admin+ct` on `wait="CHR Login: "`). Newer CHR prints `CHR Login:`, which the stock script does not match, so bootstrap loops forever. Harmless on 7.16.2, needed if you ever move to a build that prints it.

The `mikrotik` node, its `core:eth4` / `10.250.4.1` link, and `configs/mikrotik/config.auto.rsc` are already in the topology. The config uses RouterOS 7.16.2 BGP syntax (`as=`/`router-id`/`local.address` on the connection, no instance — the instance model is 7.20+). On some boots `config.auto.rsc` applies only partially; if the data-plane address or BGP session is missing, re-apply it over SSH (`admin`/`admin`).

### Huawei CE12800 — build notes (four traps)

The image is a QEMU VM (not a container) wrapped with vrnetlab. It needs KVM but not nested Intel VMX, so it boots on this AMD host. Build it with vrnetlab's `huawei_vrp` target: rename the disk to `huawei_ce12800-<version>.qcow2`, drop it in `vrnetlab/huawei/huawei_vrp/`, and `make`. The result is tagged `vrnetlab/huawei_vrp:ce12800-<version>` — the image the `huawei` node references.

1. **Login is `admin` / `admin`.** vrnetlab wipes the image's built-in user during console bootstrap and configures its own. containerlab's `huawei_vrp` kind sets `admin`/`admin`, not vrnetlab's documented `vrnetlab`/`VR-netlab9`.
2. **GE ports are L2 switchports.** The data port `GE1/0/0` must be made routed with `undo portswitch` before it takes an IP, and the CE12800 is a two-stage-commit switch, so every change needs `commit`. `scripts/configure-huawei.py` does this (and the eBGP config) after boot; `lab-up.sh` calls it, and it is idempotent. It needs netmiko on the host.
3. **It cannot hold a full table.** The emulated control plane ingests only a few routes per second and resets on the hold timer long before ~1.1M routes converge. The core therefore caps what it advertises to this peer — the short aggregates (`<=/12`) plus the test prefixes — via a GoBGP export policy keyed to the huawei neighbour (`configs/core/gobgpd.toml`), and gives it a long hold time. Every other device still gets the full table.
4. **Structured parser gap.** With structured output on, `bgp_route` and `traceroute` parse cleanly, but `bgp_aspath` and `bgp_community` return the brief multi-route table, which the Huawei structured parser does not read, so they come back empty (issue #20).

## The table feed

`inject-table.sh` loads the best path per prefix with next hop rewritten to the core's own link address, so every route resolves. Expect about 1.09M IPv4 and 261k IPv6 prefixes on each device. Re-run `fetch-table.sh` for a fresher dump; set `COLLECTOR=rrc00` for a larger table.

The test prefixes carry every path rrc19 saw, not only the best one: 1.1.1.0/24 (13 paths), 2606:4700::/44 (11 paths) and the 5,463 prefixes AS13335 originates. `scripts/filter-mrt.py` cuts them from the dump into `data/testset-bview`, `inject-table.sh` loads that subset with all paths on top of the best-path table, and the core sends them over ADD-PATH (`send-max` in `configs/core/gobgpd.toml`). FRR, VyOS and Arista receive ADD-PATH by default; BIRD (`add paths rx`) and OpenBGPD (`announce add-path recv yes`) are configured for it. MikroTik CHR 7.16 does not negotiate ADD-PATH and gets the best path only. Huawei has ADD-PATH off and stays on its capped feed. All paths for the whole table is not offered: rrc19 averages about 9 paths per prefix, roughly 12M paths, which neither the core nor the devices can hold.

## Reproducing issue #19 (traceroute truncation)

`./scripts/silent-hop.sh on` makes the core drop ICMP time-exceeded, so hops go silent and the 2 s read timeout can cut traceroute output short. `off` restores it.

## VRF test setup (issue #50)

The VRF checks use a VRF named `LAB` on five devices. It holds `198.51.100.0/24` and `2001:db8:100::/48` as Null0/blackhole static routes, originated into BGP, plus a `192.0.2.100/32` loopback for ping and traceroute. Arista and FRR load VRF `LAB` from their startup configs (`configs/arista/ceos.cfg`, `configs/frr/frr.conf`; the topology creates the FRR kernel VRF). The setup is runtime-only on Huawei, VyOS and MikroTik, so it is lost when those nodes restart. Reapply it with these commands:

- Arista: `vrf instance LAB`, `ip routing vrf LAB`, `ipv6 unicast-routing vrf LAB`, the two `ip[v6] route vrf LAB ... Null0` statics, `router bgp 65007` / `vrf LAB` with `rd 65007:100`, `router-id 10.250.7.100` and both `network` statements (IPv6 under `address-family ipv6`), and `interface Loopback100` / `vrf LAB` / `ip address 192.0.2.100/32`.
- FRR: `ip link add LAB type vrf table 100 && ip link set LAB up` in the container, then in vtysh the two blackhole statics with `vrf LAB` and `router bgp 65001 vrf LAB` with both `network` statements.
- VyOS: `set vrf name LAB table 100`, the two `set vrf name LAB protocols static route[6] ... blackhole`, `set vrf name LAB protocols bgp system-as 65005` with both `network` statements, and `set interfaces dummy dum100 vrf LAB address 192.0.2.100/32`.
- Huawei: `ip vpn-instance LAB` with `route-distinguisher 65008:100` for `ipv4-family` and `ipv6-family`, the two `ip[v6] route-static vpn-instance LAB ... NULL0`, `bgp 65008` / `ipv4-family vpn-instance LAB` and `ipv6-family vpn-instance LAB` with the `network` statements, and `interface LoopBack100` / `ip binding vpn-instance LAB` / `ip address 192.0.2.100 32`.
- MikroTik: `/interface bridge add name=lab-vrf`, `/ip vrf add name=LAB interfaces=lab-vrf` and `/ip address add address=192.0.2.100/32 interface=lab-vrf`. RouterOS needs a BGP peer inside the VRF before BGP routes appear there, and the core has none, so BGP VRF queries are validated with `vrf: main`, which reads the full lab table.

Both Ultraglass instances already list `lab-arista-vrf` and `lab-frr-vrf`. For another router, add a second entry with a different `name` and `vrf: LAB`.

## 3.4.0 release candidate features (issue #88)

Both Ultraglass instances are configured so each feature merged since 3.3.1 has a working example. Run a release candidate with `./lab-up.sh --image wilhelmza/ultraglass:3.4.0-rc.2`. The structured instance is http://127.0.0.1:8001 and the text instance is http://127.0.0.1:8002. Enable the core BGP sessions for Arista, FRR and Cisco IOL first (see [BGP session control](#bgp-session-control)).

- **VRF locations (#50).** Config: `vrf: LAB` on `lab-arista-vrf` and `lab-frr-vrf` in both `devices.yaml` files. Test: select `lab-arista-vrf`, query BGP Route `198.51.100.1`. The result shows `198.51.100.0/24` from VRF `LAB`. Query the same target on `lab-arista`; the default VRF does not hold it. `lab-frr-vrf` offers BGP queries only, because FRR has no VRF form for ping or traceroute.
- **Directive variables (#52).** Config: `lab-bgp-summary` in both `directives.yaml` files, attached to `lab-arista`. Test: select `lab-arista` and BGP Summary. The form shows an Address Family select (required) and a VRF select (optional). Choose IPv4 for `show ip bgp summary`, or IPv4 and LAB for `show ip bgp summary vrf LAB`. Over the API, send `"queryType": "lab-bgp-summary", "queryTarget": "null", "queryVariables": {"family": "ipv6"}`. A directive without a field still needs a target; the UI sends `null`. A missing `family` or a value outside the list returns an input error.
- **VyOS 1.3 (#51).** Not in the lab. No VyOS 1.3 image is available, so `platform: vyos_1_3` is untested here.
- **Server-side DNS (#48).** Config: `web.dns_provider.name: server` on the structured instance; `cloudflare` on the text instance. Test: query BGP Route with target `one.one.one.one` on each instance. The structured instance resolves through `/api/dns`; the text instance resolves in the browser through Cloudflare.
- **My IP modes (#49, #90).** Config: no `web.my_ip` key on the structured instance, so it uses the default, `server`; `external` on the text instance. Test: open the target field's My IP button on each instance. `server` fills the address the server sees without a prompt. `external` asks for confirmation before it contacts myip.wtf.
- **Self-hosted fonts (#49).** No config: the UI build downloads the configured fonts. Test: `docker exec clab-ultraglass-ultraglass ls /etc/hyperglass/static/fonts` lists `body.css`, `mono.css` and the font files. Without internet access, the UI falls back to Google Fonts links.
- **Cisco IOS structured BGP (#83, #84).** Config: `structured_output: true` on `lab-iol` in the structured instance. `lab-ioll2` stays text-only for comparison. Test: query BGP Route `1.1.1.1` on `lab-iol` and `lab-ioll2`. `lab-iol` shows a table, `lab-ioll2` shows device text. An IPv6 address target returns an input error on both, because IOS accepts only an IPv6 prefix such as `2606:4700::/44`.
- **SSH session logs (#45).** Config: `logging.session_log: true` on the structured instance. Test: run any query, then `ls configs/ultraglass/logs/`. Each device gets one file per day, named `<device>-<YYYYMMDD>.log`.
- **Paging control (#44).** Config: none; `disable_paging` defaults to `true` on every device. Test: a long Arista or Cisco result arrives complete, without `--More--` prompts.

Smoke test both instances after a change: `python3 scripts/smoke-test.py` and `python3 scripts/smoke-test.py --text`.

## Capturing parser fixtures

`configs/ultraglass/config.yaml` enables `logging.samples`, so every query appends the raw device output and the parsed result to `configs/ultraglass/logs/`. Use these to build parser regression fixtures (issue #25).

## Test suite

`tests/` holds a pytest integration suite that queries every feature of each running device and asserts the result shape. Bring a device up first, then run the matching tests:

```sh
./lab-up.sh frr
python3 -m pytest tests/ -k frr -v     # tests for devices that are not running are skipped
```

Each case is one (device, query). Known, filed bugs are marked xfail with their issue number, so the suite stays green until a fix lands, then flags the xpass. Dataplane queries (ping, traceroute) are tested IPv4 only, because the lab core has no IPv6 egress. The 42 cases cover bgp_route, bgp_aspath, bgp_community, ping and traceroute (v4 and v6 where relevant) across FRR, BIRD, OpenBGPD, MikroTik, Arista, VyOS and Huawei.

## Tear down

```sh
./lab-down.sh
```
