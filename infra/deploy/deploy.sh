#!/bin/sh
# Выкладка на VPS (запускать на сервере из каталога репозитория): межсетевой экран, сеть и образ песочниц, стек.
# Перед первым запуском: infra/docker/.env (см. .env.example) и вставка Caddyfile.snippet в Caddyfile.
set -eu
cd "$(dirname "$0")/../.."
FREE_GB=$(df -BG --output=avail / | tail -1 | tr -dc 0-9)
if [ "$FREE_GB" -lt 5 ]; then
    echo "свободно ${FREE_GB} ГБ — для сборки образов нужно ≥ 5 ГБ; освободите место или соберите вне сервера"
    exit 1
fi
# 1) экран — раньше песочниц; служба поднимает его при загрузке до Docker
cat > /etc/systemd/system/trainer-sandbox-firewall.service <<UNIT
[Unit]
Description=Trainer sandbox egress firewall
Before=docker.service
[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/bin/sh $(pwd)/infra/deploy/sandbox-firewall.sh
Restart=on-failure
[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now trainer-sandbox-firewall.service
sh infra/deploy/sandbox-firewall.sh
# 2) сеть песочниц: закреплённые мост и подсеть, без связи между контейнерами
docker network inspect trainer-sandbox >/dev/null 2>&1 || docker network create --subnet 172.31.250.0/24 \
    -o com.docker.network.bridge.name=trbr-sandbox -o com.docker.network.bridge.enable_icc=false trainer-sandbox
# 3) образ песочницы и стек
docker build -t trainer-sandbox:1 sandbox/image
docker compose -f infra/docker/docker-compose.yml --env-file infra/docker/.env up -d --build
# 4) Caddy numbermania — в сеть тренажёра (только он и тренажёр)
docker network connect trainer-edge numbermania-caddy-1 2>/dev/null || true
docker compose -f infra/docker/docker-compose.yml --env-file infra/docker/.env ps
