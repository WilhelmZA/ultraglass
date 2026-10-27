#!/bin/sh
# BIRD 2 device under test. The looking glass logs in as root, because birdc
# needs write access to the control socket.
mkdir -p /run/bird
bird -c /etc/bird.conf -s /run/bird.ctl
exec /usr/sbin/sshd -D -e
