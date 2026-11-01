#!/bin/sh
# Песочницы учеников: только интернет. Правила привязаны к мосту trbr-sandbox (имя и подсеть закреплены при
# создании сети), поэтому действуют и до появления сети — закрыто по умолчанию. Закрыты хост, частные сети,
# link-local (метаданные облака) и другие docker-сети. Идемпотентно.
set -eu
BR=trbr-sandbox
iptables -N DOCKER-USER 2>/dev/null || true   # Docker переиспользует цепочку, если она уже есть
iptables -N TRAINER-SANDBOX 2>/dev/null || iptables -F TRAINER-SANDBOX
iptables -A TRAINER-SANDBOX -m conntrack --ctstate ESTABLISHED,RELATED -j RETURN
for dst in 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16 169.254.0.0/16 100.64.0.0/10 127.0.0.0/8; do
    iptables -A TRAINER-SANDBOX -d "$dst" -j DROP
done
iptables -A TRAINER-SANDBOX -j RETURN
iptables -C DOCKER-USER -i "$BR" -j TRAINER-SANDBOX 2>/dev/null || iptables -I DOCKER-USER -i "$BR" -j TRAINER-SANDBOX
# до самого хоста (не через FORWARD): любые его адреса и порты
iptables -C INPUT -i "$BR" -j DROP 2>/dev/null || iptables -I INPUT -i "$BR" -j DROP
echo "sandbox firewall: $BR → только интернет"
