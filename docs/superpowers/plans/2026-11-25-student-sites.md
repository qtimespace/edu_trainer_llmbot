# Сайты учеников — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** сайт ученика открывается по `https://edu.qfenek.com/s/<логин>/` прямо из его папки, публикацию включает преподаватель.

**Architecture:** API отдаёт файлы из домов учеников (`/srv/trainer/homes` → в контейнер API `/homes:ro`); выбор
папки и флаг публикации — в `group_students`. Caddy пропускает `/s/*` в API. Панель: блок «Сайт» у ученика для
преподавателя, строка «Твой сайт» у ученика.

**Tech Stack:** FastAPI, SQLAlchemy `text()`, Alembic, Next.js 16 + vitest, Caddy.

**Spec:** `docs/superpowers/specs/2026-11-25-student-sites-design.md`

## Global Constraints
- Адрес: `/s/<логин>/`, логин без учёта регистра. Ссылка = `settings.public_origin + "/s/" + login + "/"`.
- По умолчанию `site_published = false`, `site_dir = NULL`.
- Отдаём только файлы с расширениями: html htm css js mjs json txt svg png jpg jpeg gif webp ico woff woff2 ttf; > 5 МБ — 404.
- Каждый ответ `/s/*` (и 404 тоже): `Content-Security-Policy: sandbox allow-scripts allow-forms allow-popups allow-modals`,
  `X-Content-Type-Options: nosniff`, `Cache-Control: no-cache`.
- Скрытые сегменты (`.`-начало), `..`, ярлыки за пределы папки сайта (и сама папка-ярлык за пределы дома) — 404.
- Дом ученика: `<homes_dir>/seat<N>/student`. Настройка `TRAINER_HOMES_DIR` (`homes_dir: Path`, по умолчанию `/srv/trainer/homes`).
- Python 3.12, тесты `python -m uv run pytest`; панель `npm run typecheck && npm test && npm run build` (из пути с `G:`).

## Review Focus
1. Папка `site_dir` — ярлык на `../../seat2/student` → 404, а не чужой сайт (тест в Task 2).
2. Логин в другом регистре (`/s/NikitoSS/`) → тот же сайт (Task 2).
3. `/s/nikitoss` без слэша → 307 на `/s/nikitoss/`, иначе относительные ссылки страницы ломаются (Task 2).
4. Имя файла по-русски / с пробелом (`/s/x/%D0%BE.html`) → отдаётся (Task 2).
5. Сайт выключили — тут же 404, без кэша (Task 2: снять флаг → 404).

---

### Task 1: настройки сайта у ученика

**Files:**
- Create: `infra/migrations/versions/0006_student_sites.py` — `ALTER TABLE group_students ADD COLUMN site_dir TEXT, ADD COLUMN site_published BOOLEAN NOT NULL DEFAULT false`
- Modify: `packages/trainer/classroom/groups.py`, `packages/trainer/settings.py`, `apps/api/group.py`
- Create: `packages/trainer/sites.py` (часть: `suggest_dir`, `valid_dir`, `home_of`)
- Test: `tests/classroom/test_sites_settings.py`

**Interfaces — Produces:**
- `Student` + поля `site_dir: str | None`, `site_published: bool`.
- `GroupStore.set_site(account_id, site_dir: str | None, published: bool) -> None`
- `GroupStore.student_by_login(login: str) -> Student | None` (`lower(a.login) = lower(:l)`)
- `Settings.homes_dir: Path = Path("/srv/trainer/homes")`
- `sites.home_of(homes_dir: Path, seat: int) -> Path` = `homes_dir / f"seat{seat}" / "student"`
- `sites.valid_dir(d: str) -> bool` — `^[A-Za-z0-9_][A-Za-z0-9._ -]*(/[A-Za-z0-9_][A-Za-z0-9._ -]*)*$`, ≤ 200 символов (первый символ сегмента не точка).
- `sites.suggest_dir(home: Path) -> str | None` — первая по алфавиту не скрытая папка глубиной 1–2 с файлом `index.html`.
- `GET /group/students/{id}/site` → `{"site_dir", "published", "suggested", "url"}`; `PUT` тот же путь, тело `{"site_dir": str|null, "published": bool}` → то же; неверная папка → 422; `published=true` без папки → 409.

- [ ] **Step 1: тесты** — `test_site_is_off_by_default`, `test_teacher_sets_folder_and_publishes` (PUT → GET отдаёт `url == "http://localhost:3000/s/kid1/"`), `test_bad_folder_rejected` (`"../x"`, `".ssh"`, `"/etc"` → 422), `test_publish_without_folder_409`, `test_suggest_finds_index` (tmp_path: `site-maket/index.html`, `.hidden/index.html` → `"site-maket"`; пусто → `None`), `test_student_by_login_ignores_case`, `test_student_cannot_touch_site_settings` (403). `homes_dir` в тестах — подмена через `monkeypatch.setenv("TRAINER_HOMES_DIR", tmp_path)` + `get_settings.cache_clear()` (как принято в conftest; если там иначе — как там).
- [ ] **Step 2:** запустить → FAIL (нет колонок/маршрутов).
- [ ] **Step 3:** миграция, поля, `set_site`, `student_by_login`, `sites.py` (три функции), маршруты в `apps/api/group.py`.
- [ ] **Step 4:** `python -m uv run pytest tests/classroom -q` → PASS; весь `pytest -q` → PASS.
- [ ] **Step 5:** commit `feat(sites): the teacher picks a student's site folder and turns publishing on`.

### Task 2: отдача сайта `/s/<логин>/…`

**Files:**
- Modify: `packages/trainer/sites.py` — `resolve(home: Path, site_dir: str, path: str) -> Path | None`, `CONTENT_TYPES: dict[str, str]`, `MAX_BYTES = 5 * 1024 * 1024`
- Create: `apps/api/sites.py` (router без префикса, без авторизации), подключить в `apps/api/main.py`
- Test: `tests/classroom/test_sites_serve.py`

**Interfaces:** Consumes Task 1. `resolve`: `root = (home/site_dir).resolve()` обязан лежать внутри `home.resolve()` и быть каталогом; любой сегмент `path`, начинающийся с `.` или пустой в середине, → `None`; `target = (root/path).resolve()`, обязан быть внутри `root`; каталог → `target/"index.html"` (снова resolve + проверка); файл, суффикс (lower) в `CONTENT_TYPES`, размер ≤ `MAX_BYTES`, иначе `None`.
Маршруты: `GET /s/{login}` → 307 на `/s/{login}/`; `GET /s/{login}/{path:path}` → `FileResponse` с типом из `CONTENT_TYPES` (`text/html; charset=utf-8` и т. п.) или `HTMLResponse(404, "Сайт ещё не опубликован…")`. Заголовки из Global Constraints на всех ответах `/s/*`.

- [ ] **Step 1: тесты** — `test_published_site_serves_index_and_files`, `test_unpublished_is_404`, `test_turning_off_is_immediate`, `test_login_case_insensitive`, `test_no_slash_redirects`, `test_hidden_and_dotdot_404` (`/.bash_history`, `/../.ssh/id`, `/%2e%2e/x`), `test_symlink_outside_folder_404` (файл-ярлык на `home/секрет.txt` и папка-сайт-ярлык на соседний `seat2`), `test_unknown_type_and_big_file_404`, `test_cyrillic_filename_served`, `test_security_headers_on_every_answer` (200 и 404).
- [ ] **Step 2:** → FAIL.
- [ ] **Step 3:** реализация.
- [ ] **Step 4:** `pytest -q` → PASS.
- [ ] **Step 5:** commit `feat(sites): serve a student's published site at /s/<login>/ — static files only, sandboxed from the panel`.

### Task 3: панель

**Files:**
- Create: `admin/components/SiteCard.tsx` — для преподавателя: поле «Папка сайта» (placeholder = `suggested`, кнопка «Взять …» подставляет), переключатель «Опубликован», «Сохранить», ссылки «Открыть» (новая вкладка) и «Копировать адрес» (`navigator.clipboard`).
- Create: `admin/lib/site.ts` + `site.test.ts` — `type SiteInfo = { site_dir: string | null; published: boolean; suggested: string | null; url: string }`, `siteStatus(s: SiteInfo): "off" | "on" | "nofolder"` (тест на три случая).
- Modify: `admin/app/(app)/group/[id]/page.tsx` — `<SiteCard studentId={id} />` под `AttentionCard`.
- Modify: `apps/api/sites.py` — `GET /me/site` (ученик) → `{"url": str | null}` (null, если не опубликован); тест `test_student_sees_own_site_url` в `tests/classroom/test_sites_serve.py`.
- Modify: `admin/app/(app)/room/page.tsx` — если `url`: строка «Твой сайт: <ссылка>» над «Мои задания».
- Modify: `admin/next.config.mjs` — rewrite `/s/:path*` → `${api}/s/:path*` (для разработки).

- [ ] Step 1: тесты (`site.test.ts`, `test_student_sees_own_site_url`) → FAIL.
- [ ] Step 2: реализация → `npm run typecheck && npm test && npm run build` PASS, `pytest -q` PASS.
- [ ] Step 3: commit `feat(sites): Site card for the teacher, "your site" link for the student`.

### Task 4: выкладка

**Files:**
- `infra/docker/Caddyfile` — `handle /s/* { reverse_proxy trainer-api:8000 }` перед общим `handle`.
- `infra/docker/docker-compose.yml` — у `api`: `volumes` + `"/srv/trainer/homes:/homes:ro"`, `TRAINER_HOMES_DIR: /homes`.
- `CLAUDE.md` — строка в «Конвенции» про сайты учеников (`/s/<логин>/`, `sites.py`, CSP sandbox, по умолчанию выключено).

- [ ] Step 1: правки, `pytest -q` PASS, панельные проверки PASS.
- [ ] Step 2: commit, push в `feat/queue1` и `main`; дождаться `/srv/trainer/deployed` = коммит (до этого проверить свободное место ≥ 2 ГБ).
- [ ] Step 3: на сервере: `docker exec trainer-api ls /homes/seat1/student` видит файлы; включить сайты Никиты (`site-maket`), Артёма (`site-maket`), Фёдора (`site`) через API/SQL **только после согласия преподавателя**; `curl -sI https://edu.qfenek.com/s/nikitoss/` → 200 + CSP; `/s/nikitoss/.bash_history` → 404.
