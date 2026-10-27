FROM alpine:3.22
RUN apk add --no-cache frr openssh traceroute iputils iproute2 \
    && ssh-keygen -A \
    && adduser -D -s /bin/sh lg && echo "lg:lg" | chpasswd \
    && addgroup lg frrvty \
    && addgroup lg frr \
    && sed -i "s/^bgpd=no/bgpd=yes/" /etc/frr/daemons
COPY entrypoint.sh /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
