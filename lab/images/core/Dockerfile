FROM debian:trixie-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends gobgpd iproute2 iptables iputils-ping traceroute procps \
    && rm -rf /var/lib/apt/lists/*
COPY entrypoint.sh /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
