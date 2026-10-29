FROM ghcr.io/srl-labs/vrnetlab-base:0.3.0
COPY os9.iso /os9.iso
COPY launch.py /launch.py
RUN qemu-img create -f qcow2 /os9.qcow2 30G
