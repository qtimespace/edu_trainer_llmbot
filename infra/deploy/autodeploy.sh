#!/bin/sh
# Автовыкладка (trainer-autodeploy.timer, раз в минуту): новый коммит в main с зелёным CI → git reset на него
# и deploy.sh. Ключей в GitHub нет: репозиторий публичный, сервер сам забирает код.
# Журнал: journalctl -u trainer-autodeploy. Выложенный коммит — /srv/trainer/deployed.
set -eu
REPO=qtimespace/edu_trainer_llmbot
BRANCH=${DEPLOY_BRANCH:-main}
DEPLOYED=/srv/trainer/deployed   # последний выложенный коммит
FAILED=/srv/trainer/failed       # коммит, который не выкладываем повторно (красный CI или упавший deploy.sh)
NO_CI_WAIT=900                   # нет ни одной проверки CI спустя 15 минут — выкладываем без неё

ci_state() {  # success | pending | failure — по check-runs коммита в GitHub
    curl -fsS -H 'Accept: application/vnd.github+json' "https://api.github.com/repos/$REPO/commits/$1/check-runs" |
        python3 -c '
import json, sys
runs = json.load(sys.stdin)["check_runs"]
if not runs: print("none")
elif any(r["status"] != "completed" for r in runs): print("pending")
elif all(r["conclusion"] in ("success", "skipped", "neutral") for r in runs): print("success")
else: print("failure")'
}

main() {  # тело в функции: git reset меняет этот файл, а sh дочитывает скрипт по ходу выполнения
    cd "$(dirname "$0")/../.."
    mkdir -p /srv/trainer
    exec 9>/run/trainer-autodeploy.lock
    flock -n 9 || exit 0
    git fetch -q origin "$BRANCH"
    new=$(git rev-parse "origin/$BRANCH")
    [ "$(cat "$DEPLOYED" 2>/dev/null)" = "$new" ] && exit 0
    [ "$(cat "$FAILED" 2>/dev/null)" = "$new" ] && exit 0
    state=$(ci_state "$new")
    if [ "$state" = none ] && [ $(( $(date +%s) - $(git log -1 --format=%ct "$new") )) -gt $NO_CI_WAIT ]; then
        state=success
    fi
    case "$state" in
        success) ;;
        failure) echo "CI красный — $new не выкладываю"; echo "$new" > "$FAILED"; exit 0 ;;
        *) exit 0 ;;  # CI ещё идёт
    esac
    echo "выкладываю $new: $(git log -1 --format=%s "$new")"
    git reset -q --hard "$new"  # infra/docker/.env не в git — остаётся
    if sh infra/deploy/deploy.sh; then
        echo "$new" > "$DEPLOYED"
        docker image prune -f >/dev/null  # старые слои прошлых сборок — место на диске не кончается
    else
        echo "deploy.sh упал — $new не выложен; следующий коммит попробует снова"
        echo "$new" > "$FAILED"
        exit 1
    fi
}

main "$@"
