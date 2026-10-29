# Enable IPv6 on a fresh CHR, then apply the fixture after its reboot.
:if ([/system package get [/system package find name=ipv6] disabled]) do={
    /system package enable ipv6
    /system scheduler add name=lab-ipv6-init start-time=startup on-event="/import file-name=config.auto.rsc"
    /system reboot
} else={
    :while ([:len [/interface ethernet find name=ether2]] = 0) do={ :delay 1s }
    /ip address remove [/ip address find interface=ether2]
    /ipv6 address remove [/ipv6 address find interface=ether2 dynamic=no]
    /routing bgp peer remove [/routing bgp peer find name~"fixture"]
    /ip address add address=10.251.8.1/30 interface=ether2
    /ipv6 address add address=fd00:251:8::1/64 interface=ether2 advertise=no
    /routing bgp instance set default as=65028 router-id=10.251.8.1
    /routing bgp peer add name=fixture4 remote-address=10.251.8.2 remote-as=65000 address-families=ip disabled=yes
    /routing bgp peer add name=fixture6 remote-address=fd00:251:8::2 remote-as=65000 address-families=ipv6 disabled=yes
    /system scheduler remove [/system scheduler find name=lab-ipv6-init]
}
