# Dell command-reference excerpts

These are vendor examples, not live captures. Whitespace is normalized and prompts are removed.

- `os10-route4.txt` and `os10-unnumbered.txt`: [OS10 10.5.6 show ip bgp](https://www.dell.com/support/manuals/en-om/smartfabric-os10-emp-partner/smartfabric-os-user-guide-10-5-6/show-ip-bgp?guid=guid-75c850f1-9777-4fe0-a8aa-563af4941b84&lang=en-us).
- `os9-route4.txt`: [OS9 9.14.2.4 show ip bgp](https://www.dell.com/support/manuals/en-us/dell-emc-os-9/s5048f-on-9.14.2.4-cli/show-ip-bgp?guid=guid-5eb9a9d4-3f6f-48e2-9f0e-aa1900ba20fe&lang=en-us).
- `os9-trace6.txt`: [OS9 traceroute](https://www.dell.com/support/manuals/en-in/dell-emc-os-9/z9100-on-9.14.2.4-cli/traceroute?guid=guid-ae409618-7e25-49ab-b989-78605b6fb592&lang=en-us).
- `os10-trace6.txt`: [OS10 traceroute](https://www.dell.com/support/manuals/en-au/smartfabric-os10-emp-partner/smartfabric-os-user-guide-10-5-6/traceroute?guid=guid-d0654846-3137-4bd3-868e-ac4ea902cb9b&lang=en-us).

The [OS9-to-OS10 mapping](https://www.dell.com/support/manuals/en-us/smartfabric-os10-emp-partner/techsheet-os10-5-x-os9-pub/border-gateway-protocol?guid=guid-8520ae6f-95e0-411e-986f-978c419f8d0f&lang=en-us) documents the IPv6 prefix form and explicitly marks OS10's arbitrary `regexp` query unsupported. OS10 uses its own CLI and detail format, not FRR JSON. Additional IPv6/multipath parser variants in unit tests are synthetic.
