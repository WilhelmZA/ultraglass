#!/bin/sh
# Run inside the disposable Cumulus VX guest with NVUE 5.16.
set -eu
nv set interface swp1 ip address 10.252.1.1/31
nv set interface swp1 ip address 2001:db8:252:1::1/127
nv set interface swp2 ip vrf LAB
nv set interface swp2 ip address 10.252.2.1/31
nv set interface swp2 ip address 2001:db8:252:2::1/127
nv set router bgp autonomous-system 65012
nv set router bgp router-id 10.252.0.12
nv set vrf default router bgp neighbor 10.252.1.0 remote-as 65000
nv set vrf default router bgp neighbor 2001:db8:252:1:: remote-as 65000
nv set vrf default router bgp address-family ipv4-unicast state enabled
nv set vrf default router bgp address-family ipv6-unicast state enabled
nv set vrf default router bgp neighbor 10.252.1.0 address-family ipv4-unicast state enabled
nv set vrf default router bgp neighbor 2001:db8:252:1:: address-family ipv6-unicast state enabled
nv set vrf LAB router bgp autonomous-system 65012
nv set vrf LAB router bgp router-id 10.252.0.12
nv set vrf LAB router bgp neighbor 10.252.2.0 remote-as 65000
nv set vrf LAB router bgp neighbor 2001:db8:252:2:: remote-as 65000
nv set vrf LAB router bgp address-family ipv4-unicast state enabled
nv set vrf LAB router bgp address-family ipv6-unicast state enabled
nv set vrf LAB router bgp neighbor 10.252.2.0 address-family ipv4-unicast state enabled
nv set vrf LAB router bgp neighbor 2001:db8:252:2:: address-family ipv6-unicast state enabled
nv config apply --assume-yes
