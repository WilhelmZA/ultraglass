![Ultraglass logo](hyperglass/images/ultraglass-light.svg)

Ultraglass is a network looking glass. It lets customers, peers and other engineers run BGP route, BGP community, BGP AS path, ping and traceroute queries from the routers you choose, through a web interface and a REST API, without touching the routers themselves. You decide which devices, commands, targets and result formats are public.

Ultraglass is a maintained fork of [hyperglass](https://github.com/thatmattlove/hyperglass). The product, repository, documentation and container images use the Ultraglass name. The Python package, CLI, configuration paths, environment variables and service names keep `hyperglass` so existing deployments upgrade in place.

## Add a router in four commands

The `hyperglass onboard` command writes the device entry, proves every published query against the live router, and tells you which features are still off. No hand-written YAML, no guessing at platform attributes, no finding out from a user that a query is broken.

```shell
hyperglass onboard device            # prompts for the router, validates it, writes devices.yaml
hyperglass onboard test core1        # runs every built-in query the router offers; PASS or FAIL per query
hyperglass onboard check             # reports feature settings and suggests the config lines to change
hyperglass onboard directive core1   # optional: build and test a custom command, then save it
```

| Step | What it does | What you get |
| --- | --- | --- |
| `onboard device` | Asks for address, port, platform, credential, OS version, VRF and structured output. Prompts only for the attributes the platform's built-in commands use. Enter `?` to list platform keys. | A validated entry saved to `devices.yaml` with owner-only permissions. Other entries stay untouched. |
| `onboard test DEVICE` | Sends every built-in IPv4 and IPv6 command the device offers, with default public targets you can override. | One block per query showing the command sent, fallback use, device errors and parsed field coverage, then a PASS/FAIL summary. Exit code `1` on any failure. |
| `onboard check` | Reads the configuration afresh and reports structured output, RPKI, cache, enrichment, server DNS, My IP, self-hosted fonts and per-device settings. | A PASS/OFF/UNKNOWN table with a `Set:` line for every suggested change, as a dotted config path you paste into YAML. |
| `onboard directive DEVICE` | Takes a directive ID, a command template with `{target}`, a target rule and a test target. Runs it once on the device. | A tested custom directive saved to `directives.yaml`, ready to add to the device's `directives` list. |

Every command accepts `--json` for scripting. Restart Ultraglass after a save so it loads the new entry. The full walkthrough with example sessions is in the [device onboarding guide](docs/content/configuration/onboarding.mdx).

## Features

| Area | Feature | Details |
| --- | --- | --- |
| Queries | BGP route | Look up an IPv4 or IPv6 prefix in the device's BGP table, optionally within a VRF. |
| Queries | BGP community | List routes carrying a BGP community value. |
| Queries | BGP AS path | List routes matching an AS path expression. Per-platform syntax is validated before the command is sent. |
| Queries | Ping and traceroute | IPv4 and IPv6, sourced from the device's configured source addresses. |
| Queries | Custom directives | Publish any device command with its own target rules, fixed-choice select fields, per-platform syntax and version-selected fallback commands. |
| Queries | VRF queries | Built-in VRF command forms for 14 platforms. Set `vrf` on the device entry. |
| Results | Structured BGP tables | Parsed route tables with prefix, next hop, AS path, communities, MED, local preference, weight, age and RPKI state, plus an interactive AS path graph. Opt-in per device. |
| Results | Structured traceroute | Parsed hops with per-probe RTT, loss and best, worst and last statistics per hop. |
| Results | RPKI validation | Router-reported state, or external validation through Cloudflare or your own Routinator. |
| Results | IP enrichment | ASN, organisation, country, IXP and reverse DNS for next hops and traceroute hops, inline or asynchronous. |
| Results | Community policy | Deny or permit listed communities, or append friendly names to them. |
| Results | Text output | Raw device output with configurable highlighting for devices that stay in text mode. |
| Devices | 26 built-in platforms | Directives and parsers included. See [Supported platforms](#supported-platforms). |
| Devices | Any Netmiko platform | Configure other SSH or Telnet platforms with custom directives. |
| Devices | HTTP devices | Query devices that expose an HTTP API instead of a CLI. |
| Devices | SSH proxy | Reach devices through a jump host. |
| Devices | Credentials | Password or private-key authentication, enable secrets and per-device driver settings. |
| Devices | OS version awareness | Set `os_version` so version-specific command variants are chosen and fallbacks are logged. |
| Devices | Connection tuning | Per-device timeouts, connection retries and delay factors for slow or rate-limited CLIs. |
| Onboarding | `hyperglass onboard` | Create, test and check devices and custom directives from the CLI. See [Add a router in four commands](#add-a-router-in-four-commands). |
| Onboarding | Configuration validation | Ultraglass refuses to start on a device entry that is missing an attribute its directives need, and names the field. |
| Onboarding | Inspection commands | `hyperglass devices`, `directives`, `plugins`, `params` and `settings` print the effective configuration. |
| Web UI | Responsive interface | Location, query type and target in one form. Multiple locations per query run concurrently. |
| Web UI | Hostname targets | Resolve hostnames with Cloudflare or Google DNS-over-HTTPS, a custom resolver URL, or the Ultraglass server's own resolver. |
| Web UI | My IP | Fill the target with the visitor's address. Server-seen by default, external lookup only after the visitor confirms, or hidden. |
| Web UI | Branding | Logo, theme colours, fonts, greeting modal, footer links and menus, OpenGraph image and every label and message. |
| Web UI | Self-hosted fonts | The UI build downloads fonts so visitors never contact Google Fonts. |
| API | REST API | Every published query is available at `/api/query`. |
| API | OpenAPI docs | Built-in interactive documentation with configurable title, descriptions and server URL. |
| Access control | Target rules | Prefix-list and access-list style rules per directive, including reserved, loopback and unspecified address handling. |
| Access control | Request timeouts | A configurable `request_timeout` bounds every device connection and command. |
| Operations | Caching | Redis-backed result cache with a configurable timeout. |
| Operations | Logging | File logs, SSH session logs, syslog, and HTTP webhooks for Slack, Microsoft Teams or any generic endpoint. |
| Operations | Query samples | Opt-in JSONL capture of raw and parsed query output, with size-based rotation, for debugging and parser fixtures. |
| Operations | Support bundle | `hyperglass support-bundle` gathers version, configuration and logs locally for a bug report. Nothing is sent automatically. |
| Operations | Container images | Published to Docker Hub and GitHub Container Registry on every release. Images are scanned for high and critical vulnerabilities before publication. |
| Operations | Lab | A Containerlab topology under `lab/` feeds real routing tables to virtual routers for regression testing. |

## Supported platforms

Ultraglass ships directives and parsers for 26 platforms: Arista EOS, Arrcus ArcOS, Aruba AOS-CX, BIRD, Cisco IOS and IOS XE, Cisco NX-OS, Cisco IOS-XR, NVIDIA Cumulus Linux, Dell OS9 (Force10), Dell SmartFabric OS10, Extreme EXOS, Extreme VOSS, Fortinet FortiGate, FRRouting, HPE Comware 7, Huawei VRP, IP Infusion OcNOS, Juniper Junos, MikroTik RouterOS and SwitchOS, Nokia SR OS, OpenBGPD, Palo Alto PAN-OS, SONiC, TNSR, VyOS 1.4+ and VyOS 1.3. Netmiko provides the device connectivity, so any other Netmiko platform works with custom directives.

Structured output is opt-in on every platform: set `structured_output: true` on each device. Structured BGP output is available for Arista EOS, Arrcus ArcOS, Aruba AOS-CX, BIRD, Cisco IOS, IOS-XR and NX-OS, NVIDIA Cumulus Linux, Dell OS9 and OS10, Extreme EXOS, FortiGate, FRRouting, HPE Comware 7, Huawei VRP, IP Infusion OcNOS, Juniper Junos, MikroTik RouterOS and SwitchOS, OpenBGPD, PAN-OS, SONiC and VyOS 1.4+. Structured traceroute covers these platforms and also Nokia SR OS, TNSR, Extreme VOSS and VyOS 1.3.

Built-in VRF queries support Arista EOS, Aruba AOS-CX, NVIDIA Cumulus Linux, Dell OS9 and OS10, Extreme EXOS and VOSS, FRRouting, HPE Comware 7, Huawei VRP, IP Infusion OcNOS, MikroTik RouterOS, PAN-OS, SONiC and VyOS 1.4+.

Platform keys, per-platform notes and known limits are in the [platforms guide](docs/content/platforms.mdx).

## Quick start

The repository includes a sample configuration with a fake device so you can see the application before connecting a router.

### Docker

```shell
git clone https://github.com/WilhelmZA/ultraglass.git --depth=1
cd ultraglass
mkdir -p /etc/hyperglass
cp .samples/sample_devices.yaml /etc/hyperglass/devices.yaml
docker compose up
```

Open `http://localhost:8001` once the containers are up. The sample device returns fake output. Then add your first real router with `hyperglass onboard device` inside the container.

`.samples/sample_config.yaml` is a complete `config.yaml` that sets every option, with a comment that explains each feature. Use it as a reference when you write your own.

### Manual installation

Manual installation needs Python 3.11 or later and Redis 7. Install the `ui` extra for the web UI, with Node.js 22.13 and pnpm 11 for the frontend build. The optional `performance` extra enables `uvloop`. The full procedure is in the [manual installation guide](docs/content/installation/manual.mdx).

## Documentation

- [Documentation home](docs/content/index.mdx)
- [Installation](docs/content/installation.mdx)
- [Device onboarding](docs/content/configuration/onboarding.mdx)
- [User guide](docs/content/user-guide.mdx)
- [Configuration](docs/content/configuration/overview.mdx)
- [Supported platforms](docs/content/platforms.mdx)
- [Plugins](docs/content/plugins.mdx)
- [Changelog](CHANGELOG.md)
- [Ultraglass Wiki](https://github.com/WilhelmZA/ultraglass/wiki)
- [Clear BSD license](LICENSE)

## Reporting bugs

Use the [bug report form](https://github.com/WilhelmZA/ultraglass/issues/new/choose). Include the Ultraglass version, deployment method, steps to reproduce, expected and observed behaviour, relevant configuration with secrets removed, and the output of `hyperglass onboard test` or `hyperglass support-bundle`. Review either before attaching it. Do not include device passwords, private keys, tokens or unredacted internal addresses.

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request. Changes should keep the backend and UI checks passing, preserve IPv4 and IPv6 support, and avoid hard-coding text or deployment-specific values that administrators should be able to configure.

## Acknowledgements

Ultraglass is distributed under the [Clear BSD License](LICENSE) and retains the required upstream attribution. It is built with [Netmiko](https://github.com/ktbyers/netmiko), [Litestar](https://litestar.dev), [Pydantic](https://docs.pydantic.dev/latest/), [React](https://react.dev/), [Next.js](https://nextjs.org/), [Chakra UI](https://chakra-ui.com/), [React Flow](https://reactflow.dev/), and [BGP.tools](https://bgp.tools/).
