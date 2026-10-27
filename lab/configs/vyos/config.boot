interfaces {
    ethernet eth1 {
        address 10.250.5.1/31
        address fd00:250:5::1/127
    }
}
protocols {
    bgp {
        system-as 65005
        neighbor 10.250.5.0 {
            remote-as 65000
            address-family {
                ipv4-unicast {
                }
            }
        }
        neighbor fd00:250:5:: {
            remote-as 65000
            address-family {
                ipv6-unicast {
                }
            }
        }
        parameters {
            router-id 10.250.5.1
        }
    }
    static {
        route 0.0.0.0/0 {
            next-hop 10.250.5.0 {
            }
        }
        route6 ::/0 {
            next-hop fd00:250:5:: {
            }
        }
    }
}
service {
    ssh {
        port 22
    }
}
system {
    host-name vyos
    login {
        user admin {
            authentication {
                plaintext-password admin
            }
        }
    }
}
