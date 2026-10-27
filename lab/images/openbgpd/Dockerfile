FROM alpine:3.22
RUN apk add --no-cache openbgpd openssh traceroute iputils iproute2 \
    && ssh-keygen -A \
    && mkdir -p /var/empty && adduser -S -H -h /var/empty -s /sbin/nologin _bgpd \
    && echo "root:lg" | chpasswd \
    && sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config
COPY entrypoint.sh /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
