#!/usr/bin/env python3
"""Write an MRT subset that keeps every path for the lab's test prefixes.

inject-table.sh loads the full table best-path only, then loads this subset
with all paths, so the test prefixes carry every path rrc19 saw. The subset
is the explicit prefixes below plus every prefix originated by an ORIGIN_AS.

    scripts/filter-mrt.py data/bview data/testset-bview
"""
import ipaddress
import struct
import sys

PREFIXES = {ipaddress.ip_network(p) for p in ("1.1.1.0/24", "2606:4700::/44")}
ORIGIN_AS = {13335}

TABLE_DUMP_V2 = 13
PEER_INDEX_TABLE = 1
# RIB_IPV4_UNICAST, RIB_IPV6_UNICAST and their ADD-PATH forms.
RIB_SUBTYPES = {2: 4, 4: 16, 8: 4, 10: 16}
ADDPATH_SUBTYPES = {8, 10}


def origin_as(attrs):
    """Return the last ASN of the AS_PATH (4-byte ASNs in TABLE_DUMP_V2)."""
    i, last = 0, None
    while i < len(attrs):
        flags, code = attrs[i], attrs[i + 1]
        if flags & 0x10:
            length = struct.unpack_from("!H", attrs, i + 2)[0]
            i += 4
        else:
            length = attrs[i + 2]
            i += 3
        if code == 2:
            j = i
            while j < i + length:
                count = attrs[j + 1]
                if count:
                    last = struct.unpack_from("!I", attrs, j + 2 + (count - 1) * 4)[0]
                j += 2 + count * 4
        i += length
    return last


def wanted(subtype, body):
    plen = body[4]
    raw = body[5:5 + (plen + 7) // 8].ljust(RIB_SUBTYPES[subtype], b"\0")
    net = ipaddress.ip_network((raw, plen))
    if net in PREFIXES:
        return True
    i = 5 + (plen + 7) // 8
    count = struct.unpack_from("!H", body, i)[0]
    i += 2
    for _ in range(count):
        i += 6  # peer index + originated time
        if subtype in ADDPATH_SUBTYPES:
            i += 4
        alen = struct.unpack_from("!H", body, i)[0]
        if origin_as(body[i + 2:i + 2 + alen]) in ORIGIN_AS:
            return True
        i += 2 + alen
    return False


def main(src, dst):
    kept = 0
    with open(src, "rb") as fin, open(dst, "wb") as fout:
        while header := fin.read(12):
            _, mtype, subtype, length = struct.unpack("!IHHI", header)
            body = fin.read(length)
            if mtype != TABLE_DUMP_V2:
                continue
            if subtype == PEER_INDEX_TABLE or (subtype in RIB_SUBTYPES and wanted(subtype, body)):
                fout.write(header + body)
                kept += subtype != PEER_INDEX_TABLE
    print(f"{kept} prefixes written to {dst}")


if __name__ == "__main__":
    main(*sys.argv[1:3])
