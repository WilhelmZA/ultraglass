FROM alpine:3.22
RUN apk add --no-cache bird2 openssh traceroute iputils iproute2 \
    && ssh-keygen -A \
    && echo "root:lg" | chpasswd \
    && sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config
COPY entrypoint.sh /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
