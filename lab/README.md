# Ultraglass multi-vendor lab

The main topology connects routers to a GoBGP core. Ultraglass queries them through a shared management network. A separate companion topology runs one optional appliance at a time with a small test feed.

Run the commands below from `lab/`.

## Requirements

- Docker and Containerlab.
- Passwordless sudo for Containerlab deployment and teardown.
- Python with PyYAML for the companion helper and Netmiko for router setup scripts.
- KVM for VM-based appliances.
- Enough available RAM for the selected routers and their routing tables.

## Layout

- `ultraglass-lab.clab.yml`: main topology and container settings.
- `ultraglass-platforms.clab.yml`: optional appliances and their probe.
- `ultraglass-aoscx.clab.yml`: optional AOS-CX and GoBGP lab; see [setup](configs/aoscx/README.md).
- `ultraglass-dell.clab.yml`: isolated OS9 and GoBGP acceptance lab; see [setup](configs/os9/README.md).
- `ultraglass-cumulus.clab.yml`: isolated Cumulus VX and GoBGP VRF lab; see [setup and capture instructions](configs/cumulus/README.md).
- `ultraglass-comware.clab.yml`: optional VSR1000 and GoBGP lab; see [setup](configs/comware/README.md).
- `ultraglass-ocnos.clab.yml`: optional OcNOS and GoBGP lab; see [setup](configs/ocnos/README.md).
- `configs/`: router startup configurations and both Ultraglass configurations.
- `images/`: Docker build contexts for the core and Linux routers.
- `scripts/`: build, setup and test helpers.
- `data/`: local routing dumps, runtime files and licenses; excluded from Git.

## Prepare the lab

```sh
./scripts/build-images.sh
./scripts/fetch-table.sh
```

Build the required appliance images before starting their nodes. Match the resulting image references to the topology.

```sh
sh scripts/build-junos.sh /path/to/junos.qcow2
sh scripts/build-cisco-iol.sh /path/to/reference-platform.iso
sh scripts/build-iosv.sh /path/to/iosv.qcow2
sh scripts/build-nexus.sh /path/to/nexus.qcow2
sh scripts/build-timos.sh /path/to/timos.qcow2
sh scripts/build-routeros6.sh /path/to/chr.vmdk
sh scripts/build-mikrotik.sh
sh scripts/build-huawei.sh
sh scripts/build-huawei.sh ne40e /path/to/hda.qcow2
sh scripts/build-os9.sh /path/to/ftos.iso
sh scripts/import-xrd.sh /path/to/image.tgz
sh scripts/build-platform.sh sonic
sh scripts/build-platform.sh exos
sh scripts/build-platform.sh voss
```

The XRd helper takes the inner container archive. For TiMOS, place the appliance license at `data/platforms/timos.license`.

## Start the main lab

```sh
./lab-up.sh frr                    # core, Redis, both applications and one router
PREFIXES=50000 ./lab-up.sh frr      # limit the table per address family
./lab-up.sh                        # start all main-topology routers
./lab-status.sh
```

Use the single-router form on a stopped lab. Containerlab cannot reconcile a node filter that excludes running nodes.

To select an application image, put `--image <image-reference>` before the optional router name. Without this option, both applications use the local development image. The helper recreates application containers when their selected image changes.

GoBGP holds its routing table in memory. `lab-up.sh` injects the table after each start. Use `scripts/fetch-table.sh` to refresh the input dump.

## Main-router BGP sessions

Keep both address families disabled on unused routers. Enable them for the router under test.

| Router | Number |
|---|---|
| FRR | 1 |
| BIRD | 2 |
| OpenBGPD | 3 |
| MikroTik | 4 |
| VyOS | 5 |
| Junos | 6 |
| Arista | 7 |
| Huawei | 8 |
| Cisco IOL | 9 |
| Cisco IOL-L2 | 10 |
| Huawei NE40E | 11 |

```sh
N=1
ACTION=enable                     # use disable after testing
docker exec clab-ultraglass-core gobgp neighbor "10.250.$N.1" "$ACTION"
docker exec clab-ultraglass-core gobgp neighbor "fd00:250:$N::1" "$ACTION"
```

Disabled sessions show `Idle(Admin)`. Established sessions show `Establ`. Repeat the selection after the core restarts.

MikroTik also starts with its router-side sessions `core4` and `core6` disabled. Enable them on the router with `/routing/bgp/connection enable [find name~"core"]`. Use `disable` after testing.

The core rewrites route next hops to its data-link address. Test prefixes receive multiple paths where the peer supports ADD-PATH. Both Huawei nodes receive a capped feed through the core export policy.

## Optional appliances

Start the main lab first so its management network and applications are available.

```sh
sh platform.sh start iosv
sh platform.sh status
sh platform.sh stop
```

Supported names are `sonic`, `exos`, `voss`, `xrd`, `iosv`, `nexus`, `timos`, `routeros6` and `os9`. The helper replaces the previous companion deployment before starting the selected appliance. It reserves 12 GiB for the host in addition to the appliance and probe limits.

Starting the same optional appliance after `stop` preserves its disk and restores its data link. Selecting a different appliance creates a fresh deployment and discards the previous appliance-local changes. Put repeatable settings in the startup configuration. XRd retains its committed configuration in `data/platforms/clab-ultraglass-platforms/xrd/xr-storage`.

The helper waits for SSH and verifies both fixture data links before reporting success. A failed check returns an error instead of reporting the appliance ready.

OS9 remains an experimental console appliance. Connect to `192.168.250.29:5000` with Telnet. Its container health confirms configuration loading only; SSH and data links are not operational.

### Companion BGP feed

Each optional appliance has a separate GoBGP probe. It advertises `1.1.1.0/24` and `2606:4700::/44`, with AS path `65000 13335` and community `37195:302`. Ping and traceroute targets `1.1.1.1` and `2606:4700::1111` terminate on the probe. This feed does not connect to the main core.

| Appliance | Link number | Router AS |
|---|---|---|
| SONiC | 1 | 65100 |
| EXOS | 2 | 65022 |
| VOSS | 3 | 65023 |
| XRd | 4 | 65024 |
| IOSv | 5 | 65025 |
| Nexus | 6 | 65026 |
| TiMOS | 7 | 65027 |
| RouterOS | 8 | 65028 |
| Dell OS9 | 9 | 65029 |

The appliance uses `10.251.N.1/31` and `fd00:251:N::1/127`. The probe uses `.0` and `::` on that link. VOSS takes no IPv6 prefix longer than `/64`, so it uses `10.251.3.1/30` and `fd00:251:3::1/64`, and the probe uses `10.251.3.2` and `fd00:251:3::2`. IPv6 does not pass on the VOSS VM data port.

RouterOS and Dell OS9 use `/30` and `/64` fixture links. Their probe addresses end in `.2` and `::2`.

Both probe sessions start disabled on each deployment. Enable them after enabling the appliance neighbors:

```sh
N=5
docker exec clab-ultraglass-platforms-probe gobgp neighbor "10.251.$N.1" enable
docker exec clab-ultraglass-platforms-probe gobgp neighbor "fd00:251:$N::1" enable
docker exec clab-ultraglass-platforms-probe gobgp neighbor
```

EXOS and VOSS start with their neighbors enabled. On SONiC, run `sh fixture.sh` from `configs/sonic/` on the node after boot; it moves `Ethernet0` to the lab link and adds both neighbors to the default AS 65100. On IOSv, enter `router bgp 65025` and run `no neighbor 10.251.5.0 shutdown` and `no neighbor fd00:251:5:: shutdown`. On XRd and Nexus, enter each neighbor under its BGP process and run `no shutdown`. Commit XRd changes.

After testing, disable both probe sessions and shut down both appliance neighbors. Save the appliance configuration, then run `sh platform.sh stop`.

### Platform setup notes

- IOSv uses `ip bgp-community new-format` for colon-form community queries. Its lab traceroute directive sends only the destination for IPv6.
- The optional RouterOS appliance enables its IPv6 package and reboots during first-time setup. Wait for both fixture peers to appear before testing.
- On RouterOS, enable the appliance peers with `/routing bgp peer enable [find name~"fixture"]`. Use `disable` after testing. Configuration changes save automatically.
- Cisco IOS IPv6 BGP lookups require a prefix, such as `2606:4700::/44`.
- IOL reads its partial configuration on first boot, then uses NVRAM. Run `sh scripts/save-cisco-iol.sh` after direct Containerlab deployment.
- Junos forwarding requires an online FPC. Check `show chassis fpc` after boot.
- Restart an existing main-lab node with `python3 scripts/start-node.py <node>`. This restores Containerlab data links and Linux interface settings while preserving the appliance disk.
- MikroTik uses fixed NIC addresses and accepts saved credentials after restart. Its wrapper repairs interface references left by the previous launcher.
- The `huawei` node is a CE12800 V200R005C10SPC607B607, which runs VRP 8.180 (VRPv8). Its locations use platform `huawei_vrpv8`: `lab-huawei-vrpv8` and `lab-huawei-vrpv8-vrf` (#103).
- The `huawei-ne40` node is an NE40E V800R011C00SPC607B607, also VRP 8.180, with 2 GiB RAM and 2 vCPUs. Its locations are `lab-huawei-ne40` and `lab-huawei-ne40-vrf`, also platform `huawei_vrpv8`. Build its image with `sh scripts/build-huawei.sh ne40e /path/to/hda.qcow2`, which assembles a vrnetlab `huawei_vrp` context in a temporary directory. The data port is `Ethernet1/0/0`. The lab has no classic VRP (V5) image, so the `huawei` platform key is tested only against these VRPv8 nodes (#103).
- Start one Huawei VM at a time. `scripts/start-node.py huawei-ne40` runs `scripts/configure-huawei.py huawei-ne40` after SSH answers.
- Huawei preserves its saved configuration and binds guest interfaces to PCI slots. The startup helper waits for SSH before applying the data-port configuration.
- IOL and IOL-L2 need host-side checksum offloading disabled on their management links. The startup helper reapplies this after Docker creates each link.
- Huawei data ports require routed mode and committed configuration. `lab-up.sh` calls `scripts/configure-huawei.py` after boot.
- EXOS and VOSS use the configured QEMU CPU setting. EXOS SSH can require `HostKeyAlgorithms=+ssh-rsa`.
- VOSS uses a `/30` probe link. Its password must not contain the username.
- SONiC keeps its default configuration across deployments. `configs/sonic/fixture.sh` sets the data port and the fixture neighbors.
- EXOS reads a community filter only as `AS : value`. Ultraglass converts the target.

## Management access

| Node | Address | Login |
|---|---|---|
| Core | 192.168.250.10 | Docker exec |
| FRR | 192.168.250.11 | lg / lg |
| BIRD | 192.168.250.12 | root / lg |
| OpenBGPD | 192.168.250.13 | root / lg |
| MikroTik | 192.168.250.14 | admin / admin |
| VyOS | 192.168.250.31 | admin / admin |
| Junos | 192.168.250.16 | admin / admin@123 |
| Arista | 192.168.250.17 | admin / admin |
| Huawei CE12800 (VRP 8.180, `lab-huawei-vrpv8`) | 192.168.250.18 | admin / admin |
| Huawei NE40E (VRP 8.180, `lab-huawei-ne40`) | 192.168.250.32 | admin / admin |
| IOL | 192.168.250.19 | admin / admin |
| IOL-L2 | 192.168.250.20 | admin / admin |
| SONiC | 192.168.250.21 | admin / admin |
| EXOS | 192.168.250.22 | admin / admin |
| VOSS | 192.168.250.23 | admin / Lab-Router9 |
| XRd | 192.168.250.24 | clab / clab@123 |
| IOSv | 192.168.250.25 | admin / Lab-Router9 |
| Nexus | 192.168.250.26 | admin / Lab-Router9 |
| Optional RouterOS | 192.168.250.28 | admin / Lab-Router9 |
| Dell OS9 | 192.168.250.29 | admin / Lab-Router9 |
| Companion probe | 192.168.250.30 | Docker exec |

The structured application is at `http://127.0.0.1:8001`; the text application is at `http://127.0.0.1:8002`. They use separate Redis databases. Structured results depend on the platform's available parsers.

## Test workflow

1. Start the selected router and enable its test feed.
2. Check BGP sessions and received prefixes.
3. Run route, AS-path, community, ping and traceroute queries through both applications.
4. Compare API results with direct CLI output.
5. Disable the feed and stop the optional appliance.

```sh
python3 scripts/smoke-test.py lab-iosv
python3 scripts/smoke-test.py --text lab-iosv
python3 -m pytest tests/ -k frr -v
ULTRAGLASS_LAB_TEXT=1 ULTRAGLASS_LAB_API=http://127.0.0.1:8002/api python3 -m pytest tests/ -k frr -v
```

Select devices that are running. The integration suite skips unavailable devices. Set `ULTRAGLASS_LAB_API` to choose a different API endpoint. Set `ULTRAGLASS_LAB_TEXT=1` to run the suite against the text application: each `_table` query id becomes its text id, and each structured case expects text.

Use `scripts/verify-issues.py` for mixed-device API checks and `scripts/verify-browser.py` for browser checks. Pass a local `data/` directory through `--output`. Browser checks require Playwright and Chromium.

Use `scripts/verify-policies.py` for community, RPKI and enrichment checks. Capture parser fixtures through `logging.samples` when adding parser coverage. Application logs stay under each configuration directory's ignored `logs/` folder.

Use `scripts/silent-hop.sh on` to test traceroute through a silent hop. Run it with `off` afterward.

### VRF and interface checks

The supplied Arista and FRR configurations create VRF `LAB`, and `scripts/configure-huawei.py` creates vpn-instance `LAB` on each Huawei node with LoopBack100 inside it: `192.0.2.108` and `2001:db8:100::8` on the CE12800, `192.0.2.111` and `2001:db8:100::11` on the NE40E. Select `lab-arista-vrf`, `lab-frr-vrf`, `lab-huawei-vrpv8-vrf` or `lab-huawei-ne40-vrf` for BGP checks using `198.51.100.0/24` and `2001:db8:100::/48`. FRR's VRF location offers BGP queries only.

Add another VRF location as a separate device entry with a unique name and `vrf: LAB`. Configure the corresponding VRF, routes and BGP address families on that router first.

The Arista BGP Summary directive demonstrates fixed-choice variables. Select the address family and optional VRF in the UI. For API calls, provide `queryVariables` with the configured choices.

## Tear down

```sh
sh platform.sh stop
./lab-down.sh
```

The companion helper stops its containers. The main teardown removes the main topology. Built images and local input files remain available.
