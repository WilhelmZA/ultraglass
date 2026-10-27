#!/bin/sh
# Core router: forwards lab traffic out of the management interface and serves
# the injected full table to every device under test over eBGP.
sysctl -qw net.ipv4.ip_forward=1 net.ipv6.conf.all.forwarding=1
iptables -t nat -C POSTROUTING -o eth0 -j MASQUERADE 2>/dev/null \
    || iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
exec gobgpd -f /etc/gobgp/gobgpd.toml -t toml --log-level=info
