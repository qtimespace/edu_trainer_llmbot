#!/bin/sh
# Песочницы учеников: только интернет. Из подсети trainer-sandbox закрыты хост, частные сети, link-local
# (метаданные облака) и другие docker-сети — ученик не дотянется до баз и сервисов на этом VPS.
# Идемпотентно: свою цепочку TRAINER-SANDBOX пересоздаёт; вызывается из DOCKER-USER.
set -eu
NET=${SANDBOX_NETWORK:-trainer-sandbox}
SUBNET=$(docker network inspect "$NET" -f '{{(index .IPAM.Config 0).Subnet}}')
iptables -N TRAINER-SANDBOX 2>/dev/null || iptables -F TRAINER-SANDBOX
iptables -A TRAINER-SANDBOX -m conntrack --ctstate ESTABLISHED,RELATED -j RETURN
for dst in 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16 169.254.0.0/16 100.64.0.0/10 127.0.0.0/8; do
    iptables -A TRAINER-SANDBOX -d "$dst" -j DROP
done
for ip in $(hostname -I); do
    iptables -A TRAINER-SANDBOX -d "$ip" -j DROP
done
iptables -A TRAINER-SANDBOX -j RETURN
iptables -C DOCKER-USER -s "$SUBNET" -j TRAINER-SANDBOX 2>/dev/null || iptables -I DOCKER-USER -s "$SUBNET" -j TRAINER-SANDBOX
# до самого хоста (не через FORWARD) — INPUT
iptables -C INPUT -s "$SUBNET" -j DROP 2>/dev/null || iptables -I INPUT -s "$SUBNET" -j DROP
echo "sandbox firewall: $SUBNET → только интернет"
