# Выкладка тренажёра на VPS

Сервер: `89.125.90.67`, вход `root` ключом `~/.ssh/edu_trainer_ed25519`. На сервере уже работают liberty и numbermania;
их Caddy (`numbermania-caddy-1`) держит порты 80/443 — тренажёр встаёт за него на свой поддомен.

## 0. Перед выкладкой

- SSH доступен: `ssh -i ~/.ssh/edu_trainer_ed25519 root@89.125.90.67 'nproc; free -h; df -h /'`
  (≥ 2 CPU, ≥ 4 ГБ RAM, ≥ 5 ГБ свободно на диске — иначе стоп).
- Поддомен (например `trainer.<домен>`) — A-запись на `89.125.90.67`.

## 1. payway — только с подтверждения владельца

1. `sh infra/deploy/payway-inventory.sh` — только чтение; список показать владельцу.
2. После «да»: дамп базы `docker exec payway-postgres pg_dumpall -U <user> > /root/payway-$(date +%F).sql`,
   скачать на машину разработчика (`scp`), на сервере удалить файл дампа.
3. Удалить контейнеры/тома/сети payway из списка, убрать блоки payway из Caddyfile, `caddy reload`.
4. Проверить, что liberty и numbermania отвечают.

## 2. Тренажёр

```sh
git clone https://github.com/qtimespace/edu_trainer_llmbot.git /opt/trainer && cd /opt/trainer
cp infra/docker/.env.example infra/docker/.env   # заполнить
sh infra/deploy/deploy.sh                        # экран и сеть песочниц, образ, стек, Caddy → trainer-edge
```

Вставить `infra/docker/Caddyfile.snippet` (со своим поддоменом) в Caddyfile numbermania, `docker exec
numbermania-caddy-1 caddy reload --config /etc/caddy/Caddyfile`.

Важно: `/api/*` и `/ws/*` идут из Caddy прямо в API — WebSocket терминала Next не проксирует, а API по
`X-Forwarded-For` видит настоящий IP ученика (ограничение попыток входа по IP не закрывает вход всем сразу).

## 3. Проверки на сервере

```sh
cd /opt/trainer && curl -LsSf https://astral.sh/uv/install.sh | sh && ~/.local/bin/uv sync
~/.local/bin/uv run pytest -m docker -v     # ssh в lab, лимит процессов, история, изоляция, доступ к хосту
docker stats --no-stream                    # память с запущенными песочницами
```

## 4. Прогон урока (смоук)

1. Преподаватель входит (`TRAINER_TEACHER_*`), «Модели и ключи» → ключ OpenRouter/HF → добавить модели;
   «Агенты» → модель для Методиста и Девопса (Девопсу — недорогую, стабильно отвечающую JSON).
2. «Группа»: группа на 3, два ученика (пароли входа показываются один раз).
3. «Уроки»: «Bash: ssh, ls, cd, touch, rm, права» → «Подготовить задания всем» → проверить черновики → «Одобрить всё».
4. Ученик 1 входит: в «Офисе» его комната светлая, Девопс за столом; ученик 2 не вошёл — комната тёмная.
5. Ученик 1: терминал → `ssh student@lab` (учебный пароль из «Группы»), задание → агент спрашивает, ловит ошибку,
   закрывает задание при верном результате. `rm -rf ~` → «Пересоздать мой сервер» → чистая песочница.
6. Преподаватель: клик по комнате — лента ответов LLM; клик по агенту — что он делает.
