#!/bin/sh
# Выкладка на VPS (запускать на сервере из каталога репозитория): образ песочницы, стек, межсетевой экран.
# Перед первым запуском: infra/docker/.env (см. .env.example) и вставка Caddyfile.snippet в Caddyfile.
set -eu
cd "$(dirname "$0")/../.."
FREE_GB=$(df -BG --output=avail / | tail -1 | tr -dc 0-9)
if [ "$FREE_GB" -lt 5 ]; then
    echo "свободно ${FREE_GB} ГБ — для сборки образов нужно ≥ 5 ГБ; освободите место (docker system prune) или соберите вне сервера"
    exit 1
fi
docker build -t trainer-sandbox:1 sandbox/image
docker compose -f infra/docker/docker-compose.yml --env-file infra/docker/.env up -d --build
docker network inspect trainer-sandbox >/dev/null 2>&1 || \
    docker network create -o com.docker.network.bridge.enable_icc=false trainer-sandbox
sh infra/deploy/sandbox-firewall.sh
# правила iptables не переживают перезагрузку — восстанавливаем при старте docker
cat > /etc/systemd/system/trainer-sandbox-firewall.service <<UNIT
[Unit]
Description=Trainer sandbox egress firewall
After=docker.service
Requires=docker.service
[Service]
Type=oneshot
ExecStart=/bin/sh $(pwd)/infra/deploy/sandbox-firewall.sh
[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable trainer-sandbox-firewall.service
docker compose -f infra/docker/docker-compose.yml --env-file infra/docker/.env ps
