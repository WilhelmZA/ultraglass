#!/bin/sh
# OpenBGPD device under test. The looking glass logs in as root, because
# bgpctl needs the root-owned control socket.
bgpd -f /etc/bgpd.conf
exec /usr/sbin/sshd -D -e
