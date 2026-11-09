# Changelog

This is the changelog for [WilhelmZA/ultraglass](https://github.com/WilhelmZA/ultraglass), a **fork** of [thatmattlove/hyperglass](https://github.com/thatmattlove/hyperglass). It documents Ultraglass changes, not upstream's.

The fork's own version line starts at **3.0.0** and is currently at **3.6.1**. It is based on **upstream hyperglass 2.0.4**, plus the upstream commits that had landed on upstream `main` after 2.0.4 but were never released by upstream. Upstream's version numbering is unrelated to this one; upstream's own history continues at [thatmattlove/hyperglass/blob/main/CHANGELOG.md](https://github.com/thatmattlove/hyperglass/blob/main/CHANGELOG.md).

Everything from [2.0.4](#204---2024-06-30) downward is inherited upstream history, kept verbatim for reference.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Added

- Arrcus ArcOS exact-prefix BGP lookups over ConfD OpenConfig JSON (`show network-instance ... protocol BGP BGP | display json`), named network-instance VRF forms, and structured loc-rib parsing (#80). `confd_cli` runs as the SSH login user. Live validation remains pending.

### Fixed

- Load `tnsr` devices with Netmiko's generic SSH driver so the built-in TNSR directives can run. `disable_paging` defaults to false because TNSR CLI has no `terminal length` command, and query targets are shell-quoted because `dataplane shell` runs the command through a shell (#102). Live ISO validation remains pending.

## 3.6.1 - 2026-11-09

This release patches the HIGH and CRITICAL vulnerabilities Docker Hub reported in the 3.6.0 image, and adds a Trivy image scan to CI that blocks a publish on a fixable HIGH or CRITICAL finding (#233). There is no functional change. A 3.6.0 configuration loads unchanged.

Images: `wilhelmza/ultraglass:3.6.1` and `ghcr.io/wilhelmza/ultraglass:3.6.1`. The `latest` tag on both registries now points to 3.6.1.

### Security

- Raise Python dependency pins to fixed releases: Pillow 13.0.0, PyJWT 2.15.1, anyio 4.16.0, Brotli 1.2.1, certifi 2026.10.23 and urllib3 2.8.0. typing-extensions moves to 4.16.0, which anyio 4.16.0 requires.
- Upgrade the UI test toolchain to Vitest 5.1, Vite 8.3 and jest-dom 7.0. This removes esbuild 0.19 (built with Go 1.20.12), Rollup 4.12 and tinypool 0.8 from the image.
- Add pnpm overrides for vulnerable transitive UI packages, including form-data, ws, node-fetch, minimatch, braces, cross-spawn, flatted and picomatch. Raise postcss to 8.5.32.
- Upgrade Alpine packages during the image build, and patch undici 6.29.1 and brace-expansion 5.0.12 inside npm. pnpm moves to 11.28.11.

### Added

- The Docker job builds and scans the image with Trivy before publishing. A HIGH or CRITICAL finding with a fixed version fails the job and blocks the publish.
- A weekly workflow scans the published `latest` image, and can scan any tag on demand.

### Changed

- Updated the Python package, runtime metadata, UI package, upgrade guide, installation docs and issue templates to 3.6.1.

## 3.6.0 - 2026-11-09

This release adds device onboarding and eight platforms: NVIDIA Cumulus Linux, HPE Comware 7, IP Infusion OcNOS, Aruba AOS-CX, Dell OS9, Dell SmartFabric OS10, FortiGate and PAN-OS. The `hyperglass onboard` command builds a device entry, tests the built-in commands against the device and reports which fields it returns.

3.6.0 supersedes release candidates 3.6.0-rc.1 and rc.2, whose sections below record what each candidate added. Cumulus VX 5.4, Dell OS9 9.13, Dell OS10 10.6.1.3P1 and FortiGate 7.6.8 completed live acceptance with captured device output kept as parser regression fixtures. The rc.2 lab run passed Cisco IOS structured and text queries and device onboarding. Comware, OcNOS, AOS-CX and PAN-OS have regression coverage, and their live acceptance remains pending.

Images: `wilhelmza/ultraglass:3.6.0` and `ghcr.io/wilhelmza/ultraglass:3.6.0`. The `latest` tag on both registries now points to 3.6.0.

### Upgrading from 3.5.0

A 3.5.0 configuration loads unchanged. No configuration key is removed. Structured output stays opt-in, so set `structured_output: true` on each new-platform device that should return tables. See the [upgrade guide](https://github.com/WilhelmZA/ultraglass/blob/main/docs/content/installation/upgrading.mdx).

### Changed

- Updated the Python package, runtime metadata, UI package, upgrade guide, installation docs and issue templates to 3.6.0.
- Updated the platform, device, structured output, onboarding and installation documentation for 3.6 (#230).

## 3.6.0-rc.2 - 2026-11-08

This is the second release candidate for 3.6.0. It completes FortiGate live validation for BGP route, ping and traceroute, and fixes two defects found during that run.

Images: `wilhelmza/ultraglass:3.6.0-rc.2` and `ghcr.io/wilhelmza/ultraglass:3.6.0-rc.2`. The `latest` tag remains on 3.5.0.

### Changed

- Version bumped to 3.6.0-rc.2.
- The UI package author now names the Ultraglass maintainers, matching the Python package and the documentation. 3.6.0-rc.1 still carried the upstream author (#225).

### Fixed

- FortiGate structured BGP route queries for a prefix that is not in the table now report that no matching results were found, instead of returning the device message as a successful result (#81).
- Text responses no longer start with blank lines when a query runs setup commands that print nothing, such as the FortiGate ping and traceroute options (#81).

### Validation

- FortiGate-VM64-KVM 7.6.8 has authentic captures for IPv4 and IPv6 BGP route detail, prefixes not in the table, ping and traceroute. BGP route, ping and traceroute pass through the API in structured and text modes. AS-path and community searches, VRF selection and PAN-OS remain unvalidated (#81).
