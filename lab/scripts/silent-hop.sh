#!/bin/sh
# Make the core router a silent traceroute hop, to reproduce issue #19.
# Usage: silent-hop.sh on | off
set -eu
RULE4="OUTPUT -p icmp --icmp-type time-exceeded -j DROP"
RULE6="OUTPUT -p ipv6-icmp --icmpv6-type time-exceeded -j DROP"
case "${1:-}" in
  on)
    docker exec clab-ultraglass-core sh -c "iptables -C $RULE4 2>/dev/null || iptables -A $RULE4; ip6tables -C $RULE6 2>/dev/null || ip6tables -A $RULE6"
    echo "core is now a silent hop" ;;
  off)
    docker exec clab-ultraglass-core sh -c "iptables -D $RULE4 2>/dev/null; ip6tables -D $RULE6 2>/dev/null; true"
    echo "core answers traceroute again" ;;
  *) echo "usage: $0 on|off" >&2; exit 1 ;;
esac
