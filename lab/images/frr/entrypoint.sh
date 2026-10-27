#!/bin/sh
# FRR device under test. The looking glass logs in as the unprivileged user "lg".
/usr/lib/frr/frrinit.sh start
exec /usr/sbin/sshd -D -e
