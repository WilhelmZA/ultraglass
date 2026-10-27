# CHR lab config. ether1 is vrnetlab management. ether2 is the eBGP link to the core.
/ip address add address=10.250.4.1/31 interface=ether2
/ipv6 address add address=fd00:250:4::1/127 interface=ether2 advertise=no
# Default route to the core so lab traffic (ping/traceroute targets) resolves.
/ip route add dst-address=0.0.0.0/0 gateway=10.250.4.0
/ipv6 route add dst-address=::/0 gateway=fd00:250:4::
# eBGP to the core. RouterOS 7.16.2 syntax (pre-7.20 instance model): as/router-id on the connection.
/routing/bgp/connection add name=core4 remote.address=10.250.4.0 remote.as=65000 local.role=ebgp as=65004 router-id=10.250.4.1 local.address=10.250.4.1
/routing/bgp/connection add name=core6 remote.address=fd00:250:4:: remote.as=65000 local.role=ebgp as=65004 router-id=10.250.4.1 local.address=fd00:250:4::1
# Disable the login banner so netmiko sees the prompt immediately.
/system/note/set show-at-login=no
