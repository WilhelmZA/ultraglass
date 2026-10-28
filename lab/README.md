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

MikroTik and Arista images are built separately (see their sections below). Juniper and the other VM vendors need their own images too.

## Start and stop

```sh
./lab-up.sh                        # whole lab (all vendors), injects the table
./lab-up.sh frr                    # ONE device only: core + redis + ultraglass + frr
./lab-down.sh                      # stop and remove everything (built images are kept)
./lab-status.sh                    # containers + BGP session state
```

`lab-up.sh` is safe to run after a reboot. GoBGP keeps the table in memory, so it is injected fresh on every start. The single-device form (`./lab-up.sh <name>`, one of frr, bird, openbgpd, mikrotik, arista, vyos, huawei) starts only that device plus the core, so it runs on far less RAM than the full lab.

Low-RAM machines can also cap the table size:

```sh
PREFIXES=50000 ./lab-up.sh frr     # inject 50k prefixes per family instead of the full ~1.1M
```

Two Ultraglass instances run against the same devices so every query can be cross-checked. http://127.0.0.1:8001 (`configs/ultraglass/`) sets `structured_output: true` on every device, so each platform returns whatever structured parsers it has. http://127.0.0.1:8002 (`configs/ultraglass-text/`) sets `structured_output: false` on every device and has no `structured` block, so every query returns raw device text. Each instance uses its own Redis database (1 and 2), so neither can serve the other's cached result. BIRD, OpenBGPD and VyOS have structured traceroute only; their BGP queries return text on both instances.

Query a device by name: lab-frr, lab-bird, lab-openbgpd, lab-mikrotik, lab-arista, lab-vyos, lab-huawei. Run `./scripts/smoke-test.py` for every query type against every running device.

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
| arista | arista_eos | 192.168.250.17 | admin / admin | cEOS 4.36.3M, full table, structured output |
| huawei | huawei (VRP) | 192.168.250.18 | admin / admin | CE12800 V200R005 (vrnetlab qemu), capped table, structured output |
| ultraglass | — | 192.168.250.2 | — | this repo's image, port 8001 |
| ultraglass-text | — | 192.168.250.4 | — | same image, all text, port 8002 |
| redis | — | 192.168.250.3 | — | cache only, no persistence |

Juniper, Cisco and Nokia SR OS are not built here: their images are VM-based or licensed, and the Intel-only nested-VMX vendors (Juniper vMX/vJunos, Cisco XRv9k/n9kv) will not boot on an AMD host. Add each as a `vr-*` node once its image is in place, give it a `10.250.N.1/31` link to a new `core:ethN` with a matching GoBGP neighbor, and uncomment its entry in `configs/ultraglass/devices.yaml`.

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

The image is a QEMU VM (not a container) wrapped with vrnetlab. It needs KVM but not nested Intel VMX, so it boots on this AMD host (unlike vJunos/vMX). Build it with vrnetlab's `huawei_vrp` target: rename the disk to `huawei_ce12800-<version>.qcow2`, drop it in `vrnetlab/huawei/huawei_vrp/`, and `make`. The result is tagged `vrnetlab/huawei_vrp:ce12800-<version>` — the image the `huawei` node references.

1. **Login is `admin` / `admin`.** vrnetlab wipes the image's built-in user during console bootstrap and configures its own. containerlab's `huawei_vrp` kind sets `admin`/`admin`, not vrnetlab's documented `vrnetlab`/`VR-netlab9`.
2. **GE ports are L2 switchports.** The data port `GE1/0/0` must be made routed with `undo portswitch` before it takes an IP, and the CE12800 is a two-stage-commit switch, so every change needs `commit`. `scripts/configure-huawei.py` does this (and the eBGP config) after boot; `lab-up.sh` calls it, and it is idempotent. It needs netmiko on the host.
3. **It cannot hold a full table.** The emulated control plane ingests only a few routes per second and resets on the hold timer long before ~1.1M routes converge. The core therefore caps what it advertises to this peer — the short aggregates (`<=/12`) plus the test prefixes — via a GoBGP export policy keyed to the huawei neighbour (`configs/core/gobgpd.toml`), and gives it a long hold time. Every other device still gets the full table.
4. **Structured parser gap.** With structured output on, `bgp_route` and `traceroute` parse cleanly, but `bgp_aspath` and `bgp_community` return the brief multi-route table, which the Huawei structured parser does not read, so they come back empty (issue #20).

## The table feed

`inject-table.sh` loads the best path per prefix with next hop rewritten to the core's own link address, so every route resolves. Expect about 1.09M IPv4 and 261k IPv6 prefixes on each device. Re-run `fetch-table.sh` for a fresher dump; set `COLLECTOR=rrc00` for a larger table.

The test prefixes carry every path rrc19 saw, not only the best one: 1.1.1.0/24 (13 paths), 2606:4700::/44 (11 paths) and the 5,463 prefixes AS13335 originates. `scripts/filter-mrt.py` cuts them from the dump into `data/testset-bview`, `inject-table.sh` loads that subset with all paths on top of the best-path table, and the core sends them over ADD-PATH (`send-max` in `configs/core/gobgpd.toml`). FRR, VyOS and Arista receive ADD-PATH by default; BIRD (`add paths rx`) and OpenBGPD (`announce add-path recv yes`) are configured for it. MikroTik CHR 7.16 does not negotiate ADD-PATH and gets the best path only. Huawei has ADD-PATH off and stays on its capped feed. All paths for the whole table is not offered: rrc19 averages about 9 paths per prefix, roughly 12M paths, which neither the core nor the devices can hold.

## Reproducing issue #19 (traceroute truncation)

`./scripts/silent-hop.sh on` makes the core drop ICMP time-exceeded, so hops go silent and the 2 s read timeout can cut traceroute output short. `off` restores it.

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
