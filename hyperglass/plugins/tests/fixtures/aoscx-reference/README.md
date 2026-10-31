# AOS-CX reference excerpts

These are transcribed examples from the HPE Aruba Networking AOS-CX 10.14 Command-Line Interface Guide for 6300/6400 switches ([public mirror](https://netz.schulon.org/fw/CX/Dokumentation/10.14/cli_6300-6400.pdf)). They are not live captures. Page headers are removed and whitespace is normalized.

- `route4.txt`: pages 371–372, `show bgp ipv4 unicast 10.0.0.0/16`. The wrapped community value is retained as printed.
- `trace4.txt`: page 2880, `traceroute 10.0.10.1`.
- `trace6.txt`: page 2883, `traceroute6 2001::2 source 2001::1`.

Unit tests derive IPv6 and multipath variants explicitly as synthetic cases. Capture real dual-stack, multipath and VRF responses before claiming live acceptance.
