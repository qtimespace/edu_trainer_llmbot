#!/bin/sh
# ТОЛЬКО ЧТЕНИЕ: что на сервере относится к payway. Ничего не удаляет.
echo "== контейнеры"; docker ps -a --filter name=payway --format '{{.Names}}\t{{.Image}}\t{{.Status}}'
echo "== compose-проекты"; docker compose ls -a 2>/dev/null | grep -i payway || true
echo "== тома"; docker volume ls --format '{{.Name}}' | grep -i payway || true
echo "== сети"; docker network ls --format '{{.Name}}' | grep -i payway || true
echo "== образы"; docker images --format '{{.Repository}}:{{.Tag}}\t{{.Size}}' | grep -i payway || true
echo "== Caddyfile"; grep -rn -i payway $(docker inspect numbermania-caddy-1 -f '{{range .Mounts}}{{.Source}} {{end}}' 2>/dev/null) 2>/dev/null | head -20 || true
echo "== cron"; crontab -l 2>/dev/null | grep -i payway || true; grep -rl -i payway /etc/cron* 2>/dev/null || true
echo "== systemd"; systemctl list-units --all --no-legend 2>/dev/null | grep -i payway || true
echo "== каталоги"; ls -d /opt/*payway* /root/*payway* /srv/*payway* 2>/dev/null || true
echo "== диск"; df -h / | tail -1; docker system df
