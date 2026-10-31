# Тренажёр юного разработчика (очередь 1) — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** к 3 ноября 2026 урок по bash проходит целиком: преподаватель описывает урок → методист готовит индивидуальные задания → преподаватель одобряет → ученик в браузере работает в своём контейнере и с агентами → агент проверяет результат в контейнере и закрывает задание; преподаватель видит все комнаты.

**Architecture:** новый проект в этом репозитории, куда **переносятся выбранные модули** DocOps-Intelligence (учётки/сессии, шифрование секретов, шлюз LLM, каркас панели и спрайты офиса), а не весь DocOps с последующей вычисткой — его GitLab/CREL-связность глубже, чем выгода. Бэкенд FastAPI + Postgres; фоновые вызовы LLM — потоки в процессе API (без Celery/Redis: одна группа до 5 учеников). Песочница — Docker-контейнер на ученика, управляемый API через Docker SDK; терминал — xterm.js ↔ WebSocket ↔ `docker exec`. Проверка задания — **детерминированные проверочные команды** (их пишет методист, одобряет преподаватель), результаты которых агент-тьютор получает вместе с историей команд; LLM отвечает JSON-ом, tool calling от моделей не требуется.

**Tech Stack:** Python 3.12 (uv), FastAPI, SQLAlchemy 2 (`text()`-SQL, как в DocOps), Alembic, Postgres 16, pgserver (тесты), `docker` (Python SDK), `openai` SDK (OpenRouter/HF через `OpenAICompatibleProvider`); Next.js 16 / React 19 / Tailwind 4 / vitest, `@xterm/xterm` + `@xterm/addon-fit`.

**Spec:** `docs/superpowers/specs/2026-10-30-edu-trainer-design.md`. Источник переносимого кода: `g:\Users\Skolpakov\IdeaProjects\DocOps-Intelligence\` (далее `DOCOPS/`).

## Global Constraints

- Группа: **2–5** учеников; одновременно одна группа; интерфейс и тексты — на русском.
- Роли: `teacher` и `student`. Ученик никогда не получает ключи LLM, настройки агентов, чужие задания/комнаты/контейнеры, задания в статусе `draft`.
- Свет в комнате и агенты в ней — **только когда ученик онлайн** (пинг не старше 40 с).
- Задание попадает ученику только после одобрения преподавателем.
- Агент не выдаёт готовых решений; задание закрывается (`done`) только если **все** проверочные команды прошли.
- Песочница: отдельный контейнер на ученика, лимиты памяти/CPU/процессов, без Docker-сокета, без связи с другими контейнерами; выход в интернет есть; домашняя папка живёт до пересоздания.
- Ssh-урок: ученик набирает `ssh` **в браузерном терминале**; наружу ssh-вход для учеников не открывается.
- Провайдеры LLM: адаптеры DocOps как есть; преподаватель подключает **OpenRouter** и **Hugging Face**.
- Секреты DocOps (`.env`, `.local-panel/secrets.env`) не копировать. Ключи LLM — только AES-GCM (`SecretBox` из DocOps), наружу не отдаются.
- Python строго 3.12 (`uv python install 3.12`); env-префикс `TRAINER_`; пакет `trainer`.
- Сервер: VPS 89.125.90.67 (будет увеличен до ≥2 CPU / 4 ГБ), за существующим Caddy numbermania на отдельном поддомене; образы собираются не на сервере.

## Review Focus

1. **Чужие данные по id.** Ученик подставляет id чужого задания/комнаты/песочницы в API или WebSocket → 404, никаких данных. Тесты: Task 7 (`test_student_cannot_read_foreign_task`), Task 10 (`test_ws_rejects_foreign_or_anonymous`), Task 12 (`test_student_cannot_post_to_foreign_task`).
2. **Двойной клик / повторная отправка во время хода агента.** Второй запрос, пока ход идёт, → 409, а не второй платный вызов. Тест: Task 12 (`test_second_message_while_running_is_409`).
3. **Битый ответ модели.** Методист вернул не-JSON / пустой список / проверку без `cmd` → черновики не создаются, ошибка видна преподавателю на уроке; тьютор вернул не-JSON → ученику вежливое «агент не смог ответить, попробуй ещё раз», статус задания не ломается. Тесты: Task 8 (`test_invalid_json_sets_prep_error`), Task 12 (`test_tutor_garbage_reply_is_soft_error`).
4. **Деньги и лимиты.** Бюджет ученика исчерпан или провайдер ответил 429/402 → ученик видит понятное сообщение, расход не превышает потолок. Тест: Task 12 (`test_budget_exhausted_message`).
5. **Ученик ломает свою песочницу** (`rm -rf ~`, fork-бомба, бесконечный цикл в проверке) → проверка не висит дольше 10 с, сервер живой, «пересоздать» восстанавливает. Тесты: Task 11 (`test_check_timeout`), Task 9 docker-тест (`test_pids_limit_holds`).

---

## Карта файлов

```
pyproject.toml, alembic.ini, CLAUDE.md, .env.example
infra/migrations/env.py, infra/migrations/versions/0001_initial.py
packages/trainer/
  settings.py domain.py db.py
  security/secrets.py                      # перенос DOCOPS/packages/docops/security/secrets.py
  accounts/{models,passwords,sessions,store,seed}.py   # перенос + роль teacher|student
  llm_gateway/...                          # перенос DOCOPS/packages/docops/llm_gateway целиком
  llm/keys.py  llm/wiring.py               # ключи провайдеров, сборка шлюза на ученика
  classroom/groups.py  classroom/presence.py
  agents/store.py  agents/seed.py
  curriculum/lessons.py  curriculum/tasks.py  curriculum/methodist.py
  sandbox/backend.py  sandbox/docker_backend.py  sandbox/manager.py  sandbox/checks.py
  tutor/jobs.py  tutor/engine.py
  office.py
apps/api/
  main.py deps.py auth.py auth_local.py
  group.py lessons.py tasks.py presence.py office.py llm_settings.py agents.py sandbox.py terminal.py
sandbox/image/{Dockerfile,entrypoint.sh,bashrc.d/history.sh,motd}
admin/                                     # каркас из DOCOPS/admin, вычищенный
infra/docker/{docker-compose.yml,api.Dockerfile,web.Dockerfile,Caddyfile.snippet}
infra/deploy/{deploy.sh,payway-inventory.sh}
tests/...
```

---

### Task 1: Каркас проекта и схема БД

**Files:**
- Create: `pyproject.toml`, `alembic.ini`, `infra/migrations/env.py`, `infra/migrations/versions/0001_initial.py`, `packages/trainer/{__init__,settings,domain,db}.py`, `tests/conftest.py`, `tests/test_schema.py`, `CLAUDE.md`, `.env.example`
- Перенос: `DOCOPS/packages/docops/domain` → только `Budget` и `stable_hash` в `trainer/domain.py`; фикстура `database_url` из `DOCOPS/tests/conftest.py`

**Interfaces:**
- Produces: `Settings` (env `TRAINER_`): `database_url`, `secrets_keys`, `session_cookie_secure`, `teacher_login`, `teacher_password`, `docker_url` (по умолчанию `unix:///var/run/docker.sock`), `sandbox_image` (`trainer-sandbox:1`), `sandbox_network` (`trainer-sandbox`), `sandbox_mem` (`"384m"`), `sandbox_cpus` (`0.5`), `sandbox_pids` (`256`), `public_origin`, `llm_registry_path`, `llm_policies_dir`; `get_settings()`; `get_engine(url) -> Engine` (кэш по url); фикстуры `engine`, `clean_db` (TRUNCATE всех таблиц).
- Схема (одна миграция, `gen_random_uuid()`):
  - `accounts` — как DOCOPS 0012, но `role TEXT CHECK (role IN ('teacher','student'))` вместо `is_admin`/`last_project_id`; `sessions` (без `project_id`), `login_attempts` — как DOCOPS 0012.
  - `groups(id, name, size INT CHECK (size BETWEEN 2 AND 5), created_at)`.
  - `group_students(group_id FK, account_id FK UNIQUE, seat INT CHECK (seat BETWEEN 1 AND 5), note TEXT DEFAULT '', budget_usd NUMERIC(10,4) DEFAULT 1.0, lesson_password TEXT NOT NULL, PK(group_id, seat))`.
  - `presence(account_id PK FK, last_seen TIMESTAMPTZ)`.
  - `llm_keys(provider TEXT PK, secret TEXT, updated_at)`; `llm_models`, `ledger`, `llm_cooldowns`/таблицы лимитов — как в DOCOPS (0001 `ledger`, 0013, 0018).
  - `agents(key TEXT PK, name, kind TEXT CHECK (kind IN ('methodist','tutor')), system_prompt TEXT, route JSONB DEFAULT '[]', max_usd_per_call NUMERIC(10,4) DEFAULT 0.05, enabled BOOL DEFAULT true, updated_at)`.
  - `lessons(id, group_id FK, title, description TEXT, position INT, prep_status TEXT CHECK (prep_status IN ('idle','running','failed')) DEFAULT 'idle', prep_error TEXT DEFAULT '', created_at)`.
  - `tasks(id, lesson_id FK, student_id FK accounts, agent_key FK agents, title, statement TEXT, checks JSONB, status TEXT CHECK (status IN ('draft','todo','in_progress','waiting_student','done')), position INT, created_at, updated_at)`.
  - `task_messages(id, task_id FK, author TEXT CHECK (author IN ('student','agent','system')), agent_key TEXT NULL, text TEXT, meta JSONB DEFAULT '{}', created_at)`.
  - `agent_jobs(id, task_id FK NULL, lesson_id FK NULL, student_id FK NULL, agent_key, status TEXT CHECK (status IN ('running','done','failed')), started_at, finished_at)` + частичный UNIQUE `(task_id) WHERE status='running'`.

- [ ] **Step 1:** `uv python install 3.12`; `pyproject.toml` с зависимостями из `DOCOPS/pyproject.toml`, кроме celery/redis/tree-sitter/mcp/pyjwt; плюс `docker`.
- [ ] **Step 2: Failing test** `tests/test_schema.py::test_migration_creates_tables` — после `alembic upgrade head` в `information_schema.tables` есть все таблицы выше; `test_group_size_bounds` — INSERT `groups.size` = 1 и 6 → `IntegrityError`, 2 и 5 — ок.
- [ ] **Step 3:** Run `python -m uv run pytest tests/test_schema.py -v` → FAIL.
- [ ] **Step 4:** миграция, settings, db, conftest.
- [ ] **Step 5:** Run → PASS.
- [ ] **Step 6:** `CLAUDE.md` — что это, ссылка на спеку/план, команды (установка, тесты, миграции, запуск API/панели), правило «из DocOps переносим модулями, секреты не копируем». Commit `feat: project skeleton and schema`.

### Task 2: Учётные записи, вход, роли

**Files:**
- Перенос с правкой: `DOCOPS/packages/docops/accounts/{models,passwords,sessions,store,seed}.py` → `packages/trainer/accounts/`; `DOCOPS/packages/docops/security/secrets.py` → `packages/trainer/security/secrets.py`; `DOCOPS/apps/api/{auth,auth_local,deps}.py` → `apps/api/`
- Create: `apps/api/main.py`; Test: `tests/accounts/test_auth.py`

**Interfaces:**
- Produces: `Account(id, login, name, role: Literal["teacher","student"], active, must_change_password)`; `AccountStore.create_account(login, password, name="", role="student", must_change=False) -> Account`, `.get`, `.by_login`, `.check_password`, `.set_password`, `.set_active`; `SessionStore`/`Throttle` — как в DOCOPS без `project_id`; cookie `trainer_session`; `account_dep -> tuple[Account, Session]`; `teacher_dep -> Account` (403 не учителю), `student_dep -> Account` (403 не ученику); `seed_teacher(store, settings)` при старте (логика `DOCOPS/.../accounts/seed.py`). API: `POST /auth/login|logout|password`, `GET /auth/me` → `{account:{id,login,name,role,must_change_password}, csrf}`.
- Убрать: `Principal`, SSO, `AccessStore`, токены, проекты.

- [ ] **Step 1: Failing tests:** `test_login_sets_cookie_and_me`, `test_wrong_password_401_and_throttle_429` (11-я неудача → 429), `test_post_without_csrf_403`, `test_teacher_dep_rejects_student`, `test_seed_teacher_from_env`.
- [ ] **Step 2:** Run `python -m uv run pytest tests/accounts -v` → FAIL.
- [ ] **Step 3:** перенос и правка.
- [ ] **Step 4:** Run → PASS. Commit `feat: accounts, sessions, teacher/student roles`.

### Task 3: Группа и ученики

**Files:** Create `packages/trainer/classroom/groups.py`, `apps/api/group.py`; Test `tests/classroom/test_groups.py`

**Interfaces:**
- Consumes: `AccountStore` (Task 2).
- Produces: `GroupStore(engine)`: `.current() -> Group | None` (единственная группа), `.create(name, size) -> Group`, `.resize(size)` (ValueError, если занятых мест больше), `.add_student(login, name, note="") -> tuple[Account, str]` (вторым — сгенерированный пароль входа; `lesson_password` — отдельный, 3 слова из простого словаря через `-`), `.students() -> list[Student]`, `.update_student(account_id, note=None, budget_usd=None)`, `.student(account_id) -> Student | None`. `Student(account_id, login, name, seat, note, budget_usd, lesson_password)`.
- API (teacher): `GET /group`, `POST /group {name,size}`, `PUT /group {size}`, `POST /group/students {login,name,note}` → `{student, password}` (пароль показывается один раз; `must_change_password=false` — дети 13+, не мучаем), `PUT /group/students/{id}`, `POST /group/students/{id}/password` → новый пароль.

- [ ] **Step 1: Failing tests:** `test_create_group_size_2_to_5` (1, 6 → 422), `test_add_student_takes_next_seat`, `test_add_beyond_size_409`, `test_resize_below_occupied_409`, `test_student_cannot_call_group_api_403`.
- [ ] **Step 2:** Run → FAIL. **Step 3:** реализация. **Step 4:** Run → PASS. Commit `feat: group and students`.

### Task 4: Присутствие

**Files:** Create `packages/trainer/classroom/presence.py`, `apps/api/presence.py`; Modify `apps/api/auth_local.py` (logout); Test `tests/classroom/test_presence.py`

**Interfaces:**
- Produces: `ONLINE_WINDOW = timedelta(seconds=40)`; `PresenceStore.ping(account_id, now=None)`, `.online(account_ids, now=None) -> set[str]`. API: `POST /presence/ping` (любая роль, 204). Выход (`/auth/logout`) удаляет строку presence.

- [ ] **Step 1: Failing tests:** `test_online_within_window`, `test_offline_after_41s`, `test_logout_makes_offline`.
- [ ] **Step 2–4:** FAIL → реализация → PASS. Commit `feat: presence`.

### Task 5: Шлюз LLM, ключи провайдеров, бюджет ученика

**Files:**
- Перенос: `DOCOPS/packages/docops/llm_gateway/` целиком → `packages/trainer/llm_gateway/` (в `catalog.py` константу `DEFAULT_LLM_ENDPOINTS` перенести внутрь модуля вместо импорта из `access.models`; политики DOCOPS удалить, добавить `policies/methodist-v1.yaml` и `policies/tutor-v1.yaml` по образцу `discussion-v1.yaml`: methodist — `max_cost_usd 0.30`, `max_output_tokens 8000`; tutor — `max_cost_usd 0.05`, `max_output_tokens 1500`; `registry.yaml` — пустой `models: {}` + `provider_limits`, модели добавляет учитель через каталог)
- Перенос: `DOCOPS/apps/api/model_catalog.py` (список моделей провайдера, добавление) → часть `apps/api/llm_settings.py`
- Create: `packages/trainer/llm/keys.py`, `packages/trainer/llm/wiring.py`; Test `tests/llm/test_keys.py`, `tests/llm/test_wiring.py`

**Interfaces:**
- Produces: `PROVIDERS = ("openrouter", "hf")`; `LlmKeyStore(engine, box: SecretBox)`: `.set(provider, key)`, `.get(provider) -> str | None`, `.status() -> dict[str, bool]`, `.delete(provider)`. `build_gateway(engine, settings, *, student_id: str | None, agent_prefix="") -> LLMGateway` (провайдеры — `OpenAICompatibleProvider` с ключом из `LlmKeyStore`; ledger — `PostgresLedger(engine, user_id=student_id)`; `providers=` можно подменить в тестах). `spent_usd(engine, student_id) -> float`; `remaining_usd(engine, student_id, budget_usd) -> float`.
- API (teacher): `GET /settings/llm` → `{keys: {openrouter: bool, hf: bool}, models: [...]}`, `PUT /settings/llm/keys/{provider} {key}`, `DELETE ...`, `GET /settings/llm/offers/{provider}`, `POST /settings/llm/models`, `DELETE /settings/llm/models/{key}`. Ключ наружу не отдаётся никогда (только `bool`).

- [ ] **Step 1: Failing tests:** `test_key_roundtrip_encrypted` (в БД строка начинается с `enc:v1:`), `test_settings_never_returns_key`, `test_gateway_records_spend_on_student` (fake-провайдер → строка `ledger.user_id = student`), `test_remaining_budget`.
- [ ] **Step 2–4:** FAIL → реализация → PASS. Перенести и прогнать тесты шлюза DOCOPS: `tests/{test_gateway,test_gateway_limits,test_health_budget_ledger,test_providers,test_model_catalog,test_limits_store}.py` (убрать то, что завязано на доступы/проекты). Commit `feat: llm gateway, provider keys, student budget`.

### Task 6: Агенты

**Files:** Create `packages/trainer/agents/{store,seed}.py`, `apps/api/agents.py`; Test `tests/agents/test_agents.py`

**Interfaces:**
- Produces: `Agent(key, name, kind: Literal["methodist","tutor"], system_prompt, route: list[str], max_usd_per_call: float, enabled: bool)`; `AgentStore`: `.list(kind=None, enabled_only=False)`, `.get(key)`, `.upsert(agent)`, `.delete(key)` (409, если на агента ссылаются задания — тогда только `enabled=false`). `seed_agents(store)` при старте создаёт отсутствующих: `methodist` («Методист»), `devops` («Девопс», tutor). Промпты сидов — в `agents/seed.py`, суть:
  - методист: «готовишь задания для подростка 13+ по описанию урока и заметке об ученике; формулировки — простым языком; к каждому заданию — проверочные команды bash, которые завершаются с кодом 0 только при правильном результате и ничего не меняют; ответ — строго JSON по схеме»;
  - тьютор: «ведёшь ученика вопросами и наводками, никогда не пишешь готовую команду-решение целиком; опираешься на результаты проверок и историю команд; ответ — строго JSON `{reply, done}`».
- API (teacher): `GET /agents`, `PUT /agents/{key}`, `DELETE /agents/{key}`. Ученику агенты отдаются только как `{key,name}` в офисе.

- [ ] **Step 1: Failing tests:** `test_seed_creates_methodist_and_devops_once`, `test_student_cannot_list_agents_403`, `test_delete_referenced_agent_409`.
- [ ] **Step 2–4:** FAIL → реализация → PASS. Commit `feat: agents`.

### Task 7: Уроки и задания

**Files:** Create `packages/trainer/curriculum/{lessons,tasks}.py`, `apps/api/lessons.py`, `apps/api/tasks.py`; Test `tests/curriculum/test_tasks.py`

**Interfaces:**
- Produces: `Check(cmd: str, about: str)`; `Task(id, lesson_id, student_id, agent_key, title, statement, checks: list[Check], status, position)`; `LessonStore`: `.create(title, description)`, `.update`, `.list()`, `.get`, `.set_prep(lesson_id, status, error="")`. `TaskStore`: `.create_draft(...)`, `.replace_drafts(lesson_id, student_id, tasks)` (удаляет прежние `draft` ученика по уроку), `.update(task_id, title=, statement=, checks=, agent_key=)` (только `draft`/`todo`), `.approve(task_id)` (`draft→todo`), `.approve_lesson(lesson_id, student_id=None)`, `.set_status(task_id, status)`, `.for_student(student_id) -> list[Task]` (**без `draft`**, по уроку и позиции), `.get_for_student(task_id, student_id) -> Task | None`.
- Допустимые переходы: `draft→todo`, `todo→in_progress`, `in_progress→waiting_student`, `waiting_student→in_progress`, `in_progress|waiting_student→done`; прочие → `ValueError`.
- API teacher: `GET/POST /lessons`, `PUT /lessons/{id}`, `GET /lessons/{id}/tasks` (все ученики, сгруппировано), `PUT /tasks/{id}`, `POST /tasks/{id}/approve`, `POST /lessons/{id}/approve {student_id?}`, `DELETE /tasks/{id}`. API student: `GET /me/tasks` → без `checks` (критерии ученику не показываем), `GET /me/tasks/{id}`.

- [ ] **Step 1: Failing tests:** `test_student_never_sees_draft`, `test_student_cannot_read_foreign_task` (404), `test_student_payload_has_no_checks`, `test_invalid_transition_raises`, `test_approve_lesson_only_drafts`.
- [ ] **Step 2–4:** FAIL → реализация → PASS. Commit `feat: lessons and tasks`.

### Task 8: Методист — подготовка индивидуальных заданий

**Files:** Create `packages/trainer/curriculum/methodist.py`, `packages/trainer/tutor/jobs.py`; Modify `apps/api/lessons.py`; Test `tests/curriculum/test_methodist.py`

**Interfaces:**
- Consumes: `build_gateway` (Task 5), `AgentStore` (6), `LessonStore`/`TaskStore` (7), `GroupStore` (3).
- Produces: `JobStore`: `.start(agent_key, *, task_id=None, lesson_id=None, student_id=None) -> str | None` (None — по этому заданию уже идёт ход: частичный UNIQUE), `.finish(job_id, ok: bool)`, `.running(student_id=None) -> list[Job]`. `run_background(fn, *args)` — поток-демон с логированием исключений. `MethodistOutput` (pydantic): `tasks: list[{title: str(1..120), statement: str, agent_key: str, checks: list[Check] (1..8)}]` (1..10 заданий). `prepare_lesson(deps, lesson_id) -> None`: для каждого ученика группы — вызов шлюза (policy `methodist-v1`, `system` = промпт методиста, `user` = описание урока + заметка ученика + список tutor-агентов `{key,name}`), разбор `MethodistOutput` (выделение JSON из ```-блока допускается), `agent_key` не из списка → первый включённый tutor; `replace_drafts`. Любая ошибка (шлюз, JSON, схема) → `set_prep(lesson, "failed", "<ученик>: <причина>")`, черновики этого ученика не трогаются; успех по всем → `idle`.
- API: `POST /lessons/{id}/prepare {student_id?}` → 202; повтор при `running` → 409.

- [ ] **Step 1: Failing tests** (fake-провайдер с заготовленными ответами): `test_prepare_creates_drafts_per_student`, `test_invalid_json_sets_prep_error`, `test_unknown_agent_key_falls_back_to_tutor`, `test_prepare_twice_409`.
- [ ] **Step 2–4:** FAIL → реализация → PASS. Commit `feat: methodist prepares individual tasks`.

### Task 9: Песочница ученика

**Files:**
- Create: `sandbox/image/Dockerfile`, `sandbox/image/entrypoint.sh`, `sandbox/image/bashrc.d/history.sh`, `sandbox/image/motd`, `packages/trainer/sandbox/{backend,docker_backend,manager}.py`, `apps/api/sandbox.py`
- Test: `tests/sandbox/test_manager.py` (fake), `tests/sandbox/test_docker_backend.py` (маркер `docker`, по умолчанию пропускается; запуск на VPS: `pytest -m docker`)

**Образ** (`debian:bookworm-slim`, тег `trainer-sandbox:1`): bash, coreutils, nano, vim-tiny, less, python3, git, openssh-client, openssh-server, procps, curl. Пользователи: `lobby` (вход терминала; приглашение `lobby:~$`, в motd — «подключись к своему серверу: ssh student@lab») и `student` (пароль задаёт entrypoint из env `LESSON_PASSWORD`). `/etc/hosts`: `lab` → 127.0.0.1. sshd слушает только `127.0.0.1:22`, `PasswordAuthentication yes`, `PermitRootLogin no`. `history.sh` для обоих: `HISTTIMEFORMAT='%F %T '`, `PROMPT_COMMAND='history -a'`, `HISTSIZE=5000`. Entrypoint: выставить пароль, запустить sshd, `sleep infinity`.

**Interfaces:**
- Produces: протокол `SandboxBackend`: `.ensure(name, env, volume) -> None`, `.remove(name, volume, wipe: bool)`, `.exec(name, cmd: list[str], user: str, timeout_s: int) -> ExecResult(exit_code: int, output: str)`, `.attach_tty(name, user) -> TtySession` (`.write(bytes)`, `.read() -> bytes | None` (неблокирующе/с таймаутом), `.resize(cols, rows)`, `.close()`), `.status(name) -> Literal["running","missing","stopped"]`. `FakeBackend` (в памяти; `exec` выполняет скриптуемые ответы). `DockerBackend(settings)`: контейнер `trainer-sbx-<seat>-<id8>`, том `trainer-home-<id8>` → `/home`, `mem_limit=settings.sandbox_mem`, `nano_cpus=int(settings.sandbox_cpus*1e9)`, `pids_limit=settings.sandbox_pids`, `cap_drop=["ALL"]`, `cap_add=["CHOWN","SETUID","SETGID","AUDIT_WRITE","SYS_CHROOT","DAC_OVERRIDE","FOWNER","KILL"]` (нужны sshd/su), `security_opt=["no-new-privileges"]` **не** ставить (ломает ssh-вход), сеть `settings.sandbox_network` (создаётся при старте, bridge с `com.docker.network.bridge.enable_icc=false`), `restart_policy=unless-stopped`, без портов наружу. `exec` оборачивает команду в `timeout <timeout_s>`.
- `SandboxManager(backend, groups)`: `.ensure_for(student_id)`, `.reset(student_id)` (удалить контейнер **и том**, создать заново), `.exec_as_student(student_id, cmd, timeout_s=10) -> ExecResult`, `.tty(student_id) -> TtySession`.
- API: `POST /me/sandbox/reset` (ученик — свой), `POST /group/students/{id}/sandbox/reset` (учитель), `GET /group/students/{id}/sandbox` → `{status}`. При входе ученика (`/auth/login`, role student) — `ensure_for` в фоне.

- [ ] **Step 1: Failing tests (fake):** `test_reset_wipes_volume_and_recreates`, `test_student_resets_only_own`, `test_login_ensures_sandbox`.
- [ ] **Step 2: Docker tests (на VPS):** `test_ssh_into_lab_with_lesson_password` (`sshpass -p … ssh -o StrictHostKeyChecking=no student@lab true` из-под `lobby` → 0), `test_pids_limit_holds` (`:(){ :|:& };:` с `timeout 5` → контейнер жив, `exec echo ok` отвечает), `test_no_icc` (из одной песочницы нет TCP до другой), `test_history_written_immediately`.
- [ ] **Step 3:** FAIL → реализация → PASS (fake локально; docker — на сервере в Task 17). Commit `feat: student sandbox`.

### Task 10: Терминал в браузере (сервер)

**Files:** Create `apps/api/terminal.py`; Test `tests/sandbox/test_terminal_ws.py`

**Interfaces:**
- Consumes: `SandboxManager.tty` (Task 9), `SessionStore` (Task 2).
- Produces: `WS /ws/terminal`: аутентификация по cookie `trainer_session` (CSRF не нужен), проверка заголовка `Origin` == `settings.public_origin`; только role `student`, терминал всегда своей песочницы (никаких id в URL); пользователь tty — `lobby`. Протокол: клиент → бинарные кадры = ввод; текст `{"type":"resize","cols":N,"rows":M}`; сервер → бинарные кадры = вывод. Насос вывода — поток → `asyncio.Queue`. Закрытие WS → `TtySession.close()`.

- [ ] **Step 1: Failing tests** (`TestClient.websocket_connect`, FakeBackend с эхо-tty): `test_ws_echo_roundtrip`, `test_ws_rejects_foreign_or_anonymous` (без cookie / учитель / чужой Origin → закрыто с кодом 4401/4403), `test_resize_forwarded`.
- [ ] **Step 2–4:** FAIL → реализация → PASS. Commit `feat: terminal websocket`.

### Task 11: Проверки и история команд

**Files:** Create `packages/trainer/sandbox/checks.py`; Test `tests/sandbox/test_checks.py`

**Interfaces:**
- Produces: `CheckResult(cmd, about, passed: bool, output: str)` (output обрезан до 500 символов); `run_checks(manager, student_id, checks: list[Check]) -> list[CheckResult]` — каждая команда `bash -lc '<cmd>'` от `student`, таймаут 10 с, `passed = exit_code == 0`, таймаут/ошибка exec → `passed=False`, `output="(проверка не уложилась в 10 с)"`. `recent_history(manager, student_id, limit=40) -> list[str]` — последние строки из `/home/lobby/.bash_history` и `/home/student/.bash_history` (с метками времени, слитые по времени, с пометкой `lobby$`/`student$`).

- [ ] **Step 1: Failing tests:** `test_pass_and_fail`, `test_check_timeout`, `test_history_merges_lobby_and_student`.
- [ ] **Step 2–4:** FAIL → реализация → PASS. Commit `feat: sandbox checks and history`.

### Task 12: Тьютор — ход агента по заданию

**Files:** Create `packages/trainer/tutor/engine.py`; Modify `apps/api/tasks.py`; Test `tests/tutor/test_engine.py`, `tests/tutor/test_api.py`

**Interfaces:**
- Consumes: Tasks 5, 6, 7, 8 (`JobStore`, `run_background`), 11.
- Produces: `TutorReply(reply: str, done: bool)`; `tutor_turn(deps, task_id, student_id) -> None`:
  1. `remaining_usd <= 0` → system-сообщение «Лимит на сегодня исчерпан — позови преподавателя», статус не меняется, выход.
  2. `run_checks`, `recent_history`, последние 20 сообщений.
  3. Шлюз: policy `tutor-v1`, `agent=<agent_key>`, `task_id`, `route=agent.route or None`, `Budget(max_usd=min(agent.max_usd_per_call, remaining))`; `user` = формулировка задания + результаты проверок (`about`, ✓/✗, без `cmd`) + история + переписка.
  4. Разбор `TutorReply`; задание `done` тогда и только тогда, когда **все проверки прошли** (`reply.done` модели — только подсказка тону ответа: при непрошедших проверках `done=true` игнорируется).
  5. Сообщение агента (`meta = {checks: [...], model, cost_usd}`), статус `done` или `waiting_student`.
  6. Ошибки: `GatewayError` (`rate_limited`, `budget_exceeded`, `quota_exceeded`, прочее) или битый JSON → system-сообщение «Агент сейчас не смог ответить, попробуй ещё раз через минуту», статус `waiting_student`.
- API student: `POST /me/tasks/{id}/start` (`todo→in_progress`, ход без сообщения ученика: агент открывает разговор вопросом) → 202; `POST /me/tasks/{id}/messages {text(1..2000)}` → 202 (сохраняет сообщение, `waiting_student→in_progress`, ход); `GET /me/tasks/{id}/messages` → лента + `running: bool`. Ход уже идёт → 409. Статус `done` → 409.

- [ ] **Step 1: Failing tests** (fake-провайдер + FakeBackend): `test_start_asks_first_question`, `test_done_only_when_all_checks_pass` (модель `done=true`, одна проверка ✗ → `waiting_student`), `test_all_checks_pass_closes_task`, `test_checks_cmd_not_leaked_to_student_messages`, `test_tutor_garbage_reply_is_soft_error`, `test_budget_exhausted_message`, `test_second_message_while_running_is_409`, `test_student_cannot_post_to_foreign_task`.
- [ ] **Step 2–4:** FAIL → реализация → PASS. Commit `feat: tutor turn`.

### Task 13: Офис (API)

**Files:** Create `packages/trainer/office.py`, `apps/api/office.py`; Test `tests/test_office.py`

**Interfaces:**
- Consumes: Groups (3), Presence (4), Agents (6), Tasks (7), Jobs (8).
- Produces: `GET /office` → `{size, rooms: [Room]}`; учитель — все места `1..size` (пустое место → `student: null`), ученик — только своя комната. `Room = {seat, student: {id,name}|null, online: bool, lights: bool (= online), agents: [AgentInRoom]}`; при `online=false` → `agents: []`. `AgentInRoom = {key, name, state: "typing"|"waiting"|"idle"|"done", task: {id,title,status}|null, last_reply: str|null}`; агенты комнаты = все включённые `tutor`; состояние: идёт `agent_job` по заданию ученика с этим агентом → `typing`; есть задание `waiting_student` → `waiting`; последнее задание `done` и других в работе нет → `done`; иначе `idle`. `GET /office/rooms/{student_id}/feed?after=<iso>` (учитель) → последние 50 сообщений агентов и system по всем заданиям ученика: `{at, agent, task_title, text, model, cost_usd}` — «окно ответов LLM».

- [ ] **Step 1: Failing tests:** `test_offline_room_dark_and_empty`, `test_online_room_has_tutors`, `test_typing_state_while_job_running`, `test_student_sees_only_own_room`, `test_feed_teacher_only`.
- [ ] **Step 2–4:** FAIL → реализация → PASS. Commit `feat: office api`.

### Task 14: Панель — каркас, вход, экраны преподавателя

**Files:**
- Перенос из `DOCOPS/admin`: `package.json` (без `@xyflow/react`), `next.config.mjs` (`TRAINER_API_URL`), `tsconfig.json`, `postcss.config.mjs`, `vitest.config.ts`, `app/layout.tsx`, `app/globals.css`, `app/(auth)/login/page.tsx`, `components/{Shell,ui,Markdown}.tsx`, `lib/{api,session,poll,forms,hooks}.ts(x)` + их тесты; убрать проекты из `session.tsx`.
- Create: `lib/nav.ts` (меню по роли), `app/(app)/group/page.tsx`, `app/(app)/lessons/page.tsx`, `app/(app)/lessons/[id]/page.tsx`, `app/(app)/settings/llm/page.tsx`, `app/(app)/settings/agents/page.tsx`, `lib/{group,lessons,llm,agents}.ts` + `*.test.ts`

**Interfaces:**
- Consumes: API Tasks 2–8.
- Produces: меню учителя — «Офис», «Группа», «Уроки», «Настройки → Модели и ключи / Агенты»; ученика — «Моя комната». Экраны:
  - Группа: размер (2–5), ученики (имя, логин, заметка, бюджет, учебный пароль, статус песочницы, «Пересоздать песочницу», «Новый пароль»), пароль входа показывается один раз.
  - Уроки: список; урок — описание, «Подготовить задания» (весь класс / один ученик), статус подготовки и `prep_error`; черновики по ученикам: правка заголовка, формулировки, проверок (`cmd` + `about`), агента; «Одобрить» / «Одобрить всё ученику» / «Одобрить всё».
  - Модели и ключи: ключ OpenRouter/HF (только «задан/не задан»), добавить модель из списка провайдера.
  - Агенты: имя, тип, промпт, модели (порядок), лимит на вызов, вкл/выкл.
- Все страницы с опросом — через `lib/poll.ts`.

- [ ] **Step 1: Failing vitest:** `nav.test.ts` (`menuFor("student")` не содержит «Группа», «Уроки», «Настройки»), `lessons.test.ts` (`groupDraftsByStudent`, `canApprove(status)`), `group.test.ts` (`sizeOptions()` = [2,3,4,5]).
- [ ] **Step 2:** `cd admin && npm test` → FAIL. **Step 3:** реализация. **Step 4:** `npm run typecheck && npm test && npm run build` → PASS. Commit `feat(panel): shell and teacher screens`.

### Task 15: Панель — офис с комнатами

**Files:**
- Перенос: `DOCOPS/admin/components/office/{iso-sprites,portrait}.ts`, `DOCOPS/admin/lib/{iso,chibi,portrait-art,portrait}.ts` (+ тесты); `IsoOffice.tsx` — как образец рендер-цикла, не целиком.
- Create: `admin/lib/rooms.ts` (+ `rooms.test.ts`), `admin/components/office/RoomsOffice.tsx`, `admin/components/office/RoomFeed.tsx`, `admin/app/(app)/office/page.tsx`

**Interfaces:**
- Consumes: `GET /office`, `GET /office/rooms/{id}/feed` (Task 13); спрайты: `floorTile`, `wallBack`, `wallSide`, `desk`, `monitor(…, glow)`, `chairSeat`, `chairBack`, `drawChibi`, `furniture`.
- Produces: `roomGrid(size: number) -> {cols, rows}` (2→2×1, 3→3×1, 4→2×2, 5→3×2 с пустой клеткой); `roomLayout(room, agentCount) -> {desks, seats}` (стол на агента, максимум 4); `RoomsOffice({rooms, mode: "teacher"|"student", onAgentClick})`: каждая комната — изометрический бокс; `lights=false` → пол и стены затемнены полупрозрачным `#0b0f14` (~0.7), мониторы без свечения, агентов нет, табличка с именем ученика и «не в сети»; `lights=true` → агенты сидят за столами, `typing` — печатает, `waiting` — пузырь «?», `done` — пузырь «✓». Клик по агенту (учитель) → карточка: имя, состояние, задание, последний ответ. Учитель: справа от офиса — `RoomFeed` выбранной комнаты (опрос 3 с). Опрос `/office` — 2 с (как в DocOps).

- [ ] **Step 1: Failing vitest:** `rooms.test.ts` — `roomGrid` для 2..5; `roomLayout` с 0 агентами → без мест; `isDark({online:false})`.
- [ ] **Step 2–4:** FAIL → реализация → `npm run typecheck && npm test && npm run build` PASS. Проверить руками на стенде: 3 ученика, онлайн один → одна светлая комната с агентами, две тёмные пустые. Commit `feat(panel): rooms office`.

### Task 16: Панель — рабочее место ученика

**Files:** Create `admin/app/(app)/room/page.tsx`, `admin/app/(app)/room/tasks/[id]/page.tsx`, `admin/components/Terminal.tsx`, `admin/components/TaskChat.tsx`, `admin/lib/tasks.ts` (+ `tasks.test.ts`), `admin/lib/presence.ts`; Modify `admin/package.json` (`@xterm/xterm`, `@xterm/addon-fit`)

**Interfaces:**
- Consumes: `/me/tasks*`, `/me/sandbox/reset`, `/presence/ping`, `/office` (своя комната), `WS /ws/terminal`.
- Produces: `usePresence()` — пинг раз в 15 с, пока вкладка открыта (во всём layout `(app)` для ученика). `/room`: своя комната (`RoomsOffice mode="student"`) по центру, бэклог слева (по урокам; статусы по-русски: «к выполнению», «в работе», «ждёт тебя», «готово»). `/room/tasks/[id]`: сверху формулировка, слева `Terminal` (xterm, `FitAddon`, ресайз → WS), справа `TaskChat` (лента, поле ввода, «Отправить агентам» для `todo`; индикатор «агент думает» при `running`; блокировка отправки при `running`/`done`), кнопка «Пересоздать мой сервер» с подтверждением. Адрес WS: `NEXT_PUBLIC_WS_URL` или `wss://<host>/ws/terminal` (в проде Caddy направляет `/ws/*` прямо в API, минуя Next).

- [ ] **Step 1: Failing vitest:** `tasks.test.ts` — `statusLabel`, `canSend(task, running)`, `wsUrl(location, env)`.
- [ ] **Step 2–4:** FAIL → реализация → typecheck/test/build PASS. Commit `feat(panel): student workplace`.

### Task 17: Выкладка на VPS и прогон урока

**Files:** Create `infra/docker/{docker-compose.yml,api.Dockerfile,web.Dockerfile,Caddyfile.snippet}`, `infra/deploy/{deploy.sh,payway-inventory.sh}`, `docs/deploy.md`

**Interfaces:**
- compose (проект `trainer`): `postgres` (`postgres:16-alpine`, том `trainer-pg`, mem 256m), `api` (uvicorn 1 воркер, `/var/run/docker.sock` смонтирован, `alembic upgrade head` при старте, mem 512m), `web` (`next start`, mem 384m); сеть `trainer` + внешняя сеть Caddy numbermania (узнать имя на сервере), наружу портов нет. Песочницы создаёт `api` в сети `trainer-sandbox`.
- Caddy (вставка в Caddyfile numbermania): `<поддомен> { handle /ws/* { reverse_proxy trainer-api:8000 } handle_path /api/* { reverse_proxy trainer-api:8000 } handle { reverse_proxy trainer-web:3000 } }`.
- Сборка: образы `trainer-api`, `trainer-web`, `trainer-sandbox:1` собираются **не на сервере** (машина без Docker → GitHub Actions/другая машина с Docker; либо `docker save | ssh … docker load`) — способ выбрать по факту, записать в `docs/deploy.md`.

- [ ] **Step 1:** Доступ: SSH на 89.125.90.67 ключом `~/.ssh/edu_trainer_ed25519` работает; сервер увеличен (`nproc` ≥ 2, `free -g` ≥ 4). Иначе — стоп, сообщить владельцу.
- [ ] **Step 2:** `payway-inventory.sh` (только чтение): контейнеры/тома/сети `payway*`, вхождения `payway` в Caddyfile, cron, systemd. **Показать список владельцу и получить «да».** `pg_dump` базы payway → скачать на машину разработчика. Удалить контейнеры/тома/записи Caddy payway. Проверить, что liberty и numbermania отвечают.
- [ ] **Step 3:** Поддомен — согласовать с владельцем; DNS A-запись → 89.125.90.67.
- [ ] **Step 4:** Доставить образы, `.env` на сервере (`TRAINER_SECRETS_KEYS` сгенерировать там, `TRAINER_TEACHER_*`, `TRAINER_PUBLIC_ORIGIN`), `docker compose up -d`, вставка в Caddyfile, `caddy reload`.
- [ ] **Step 5:** `pytest -m docker` на сервере (тесты Task 9) → PASS.
- [ ] **Step 6: Прогон урока (смоук):** учитель входит; ключ OpenRouter/HF; модели для методиста и Девопса (Девопс — недорогая модель, которая стабильно отдаёт JSON); группа на 3; два ученика; урок «Bash: ssh, ls, cd, touch, rm, права» → «Подготовить» → черновики правдоподобны → одобрить. Ученик 1 входит: свет в его комнате, Девопс на месте; ученик 2 не входит — комната тёмная. Ученик 1: `ssh student@lab` с учебным паролем, задание про `Temp/test.py` → агент спрашивает, ловит ошибку, закрывает при верном результате. `rm -rf ~` → «Пересоздать» → чистая песочница. Учитель видит состояние агентов и ленту ответов LLM. Замерить память (`docker stats`) с 5 песочницами.
- [ ] **Step 7:** `docs/deploy.md` + `CLAUDE.md` (команды выкладки). Commit `feat: deploy`.

---

## Порядок и параллельность

1 → 2 → (3, 4, 5, 6 — независимы) → 7 → 8 → (9 → 10, 11) → 12 → 13; панель: 14 после 2–8, 15 после 13, 16 после 10–13; 17 последней. При нехватке времени к 3 ноября упрощается Task 15 (простые комнаты-прямоугольники вместо изометрии), а не 9–12.
