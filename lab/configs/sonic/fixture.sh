#!/bin/sh
# Run on the SONiC node after boot: moves Ethernet0 onto the lab subnet and peers
# with the GoBGP fixture. The SONiC default config keeps AS 65100.
set -eu
sudo config interface ip remove Ethernet0 10.0.0.0/31 || true
sudo config interface ip add Ethernet0 10.251.1.1/31
sudo config interface ip add Ethernet0 fd00:251:1::1/127
sudo config interface startup Ethernet0
# The SONiC vtysh wrapper runs `docker exec -it`, which fails without a TTY.
sudo docker exec bgp vtysh \
    -c 'configure terminal' \
    -c 'router bgp 65100' \
    -c 'neighbor 10.251.1.0 remote-as 65000' \
    -c 'neighbor fd00:251:1:: remote-as 65000' \
    -c 'address-family ipv4 unicast' \
    -c 'neighbor 10.251.1.0 activate' \
    -c 'neighbor 10.251.1.0 soft-reconfiguration inbound' \
    -c 'no neighbor fd00:251:1:: activate' \
    -c 'exit-address-family' \
    -c 'address-family ipv6 unicast' \
    -c 'neighbor fd00:251:1:: activate' \
    -c 'neighbor fd00:251:1:: soft-reconfiguration inbound' \
    -c 'exit-address-family'
