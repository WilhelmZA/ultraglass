# On-demand platform images

Run these appliances through `platform.sh`. The separate `ultraglass-platforms` topology shares the existing management network. The main `lab-up.sh` does not start these appliances.

```sh
sh scripts/build-platform.sh exos
sh scripts/build-platform.sh voss
sh scripts/build-platform.sh sonic
sh platform.sh start exos
sh platform.sh status
sh platform.sh stop
```

`start` stops the previous optional appliance and redeploys this companion lab with the selected appliance and a small probe container. It preserves the shared management network. Each fresh start uses a clean appliance disk, because the wrappers expect first-boot credentials. Treat appliance-local configuration as disposable. The downloaded disks and built images remain available.

The helper requires Python 3 with PyYAML. It checks `MemAvailable` before deployment and reserves 12 GiB for the host and existing applications. Only one optional appliance runs at a time. Stop the appliance after testing to release its RAM. BGP peers are not configured, so the full-table core cannot feed these appliances.

| Node | Image | Management address | Login | Guest RAM | Container RAM limit |
|---|---|---|---|---|---|
| sonic | `ultraglass-lab/sonic_sonic-vs:202505.1238524` | `192.168.250.21` | `admin` / `admin` | 4 GiB | 5 GiB |
| exos | `ultraglass-lab/extreme_exos:32.7.2.19` | `192.168.250.22` | `admin` / `admin` | 1 GiB | 2 GiB |
| voss | `ultraglass-lab/extreme_voss:9.4.0.0` | `192.168.250.23` | `admin` / `Lab-Router9` | 2 GiB | 3 GiB |

The probe uses `192.168.250.30`, with a 128 MiB limit. Its data addresses are `10.251.1.0/31`, `10.251.2.0/31`, and `10.251.3.2/30` for SONiC, EXOS, and VOSS respectively. EXOS and VOSS startup scripts configure their data interfaces at `10.251.2.1/31` and `10.251.3.1/30`. VOSS rejects a `/31` VLAN interface. This topology prepares platform appliances; it does not implement the pending Ultraglass drivers.

EXOS and VOSS use `QEMU_CPU=core2duo` for this AMD host. VOSS stalls before serial output with `-cpu host`; `core2duo` allows it to boot. Containerlab 0.82 has no dedicated Extreme kinds, so EXOS and VOSS use `generic_vm` with their platform-specific vrnetlab launchers.

The EXOS build also fixes command synchronization in the pinned wrapper. The configuration helper waits for each command's echo before its completion prompt. This prevents stale prompts from advancing the bootstrap while a command is still running. Password setup sends its command without waiting for the prompt already consumed by the helper.

SONiC retains its publisher's default configuration. To address its data port after boot, log in as `admin` and run:

```sh
sudo config interface ip add Ethernet0 10.251.1.1/31
sudo config interface startup Ethernet0
```

EXOS needs `ssh -o HostKeyAlgorithms=+ssh-rsa admin@192.168.250.22` with current OpenSSH clients. VOSS requires a password that does not contain the username. Its `admin` account therefore uses `Lab-Router9`.

## Local verification

On 29 October 2026, all three images pass SSH, version checks and data-port pings. EXOS and VOSS also pass clean-start checks with their supplied startup files. SONiC's ping check uses the manual interface commands above.

Observed idle container memory is approximately 545 MiB for EXOS, 1.76 GiB for VOSS and 2.59 GiB for SONiC. These measurements exclude a full BGP table. All optional appliances and the probe are stopped after verification. The host has 31 GiB available and no swap use at completion.

## Image verification

The build script downloads only over HTTPS from publisher-controlled sources. It verifies the references below before inspecting disk metadata and consistency in an unprivileged, network-isolated Bubblewrap sandbox. It rejects backing files and external data files. It then builds vrnetlab revision `85445edfdf366b3d5f04942a10bb5a7d22df61a7` in a separate temporary directory.

Files and inspection evidence remain under `/tmp/opencode/ultraglass-tier3-images`. Set `PLATFORM_IMAGE_DIR` to use another directory. Partial files must pass the same checksum checks before the script promotes them.

| Platform | Publisher reference | Verified checksum |
|---|---|---|
| SONiC | [Official build 1238524](https://sonic-build.azurewebsites.net/ui/sonic/pipelines/142/builds/1238524/artifacts?branchName=202505), SPDX manifest `./sonic-vs.img.gz` | SHA256 `b4225804b2098704c99e2b7c790fe6f70ebcf07fae55ded6fe63042c535c2ee8` |
| EXOS | [Extreme's README](https://github.com/extremenetworks/Virtual_EXOS), vendor-hosted `EXOS-VM_32.7.2.19.qcow2` | MD5 `eba580a2e18d2a9cc972c9ece8917ea8` |
| VOSS | [Extreme's appliance manifest](https://github.com/extremenetworks/Virtual_VOSS/blob/master/VOSSGNS3-V9.X.gns3a), vendor-hosted `FEGNS3.9.4.0.0.qcow2` | MD5 `341aef71e2dbb976e6fa6369b363789e` |

The script also pins locally calculated SHA256 hashes for the two Extreme downloads. Publisher HTTPS delivery and matching checksums establish provenance and integrity; these checks are not a malware assessment or signature verification.

## Remaining image access

| Platform | Current blocker |
|---|---|
| Dell OS10 | Dell's current download page requires account access. Mirror packages have no authenticated checksum available. Obtain the vendor virtualization ZIP and checksum before preparation. |
| Dell OS9 | No suitable virtual appliance or ready vrnetlab wrapper identified. |
| Cumulus VX | NVIDIA discontinued public standalone image distribution. An authenticated retained image is required. |
| Comware VSR1000 | The wrapper's HPE download endpoint fails TLS certificate verification. A current vendor download and checksum are required. |
| Aruba AOS-CX | The simulator download requires an HPE Networking account. |
| OcNOS | The vendor's free 365-day VM requires a registration form before download. |
| ArcOS | Request a VM image from Arrcus. |
| FortiGate / PAN-OS | Vendor VM image access and evaluation licensing are required. |

Previously downloaded IOSv, TiMOS and Nexus images retain their separate, unverified status.
