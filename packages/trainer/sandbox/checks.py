"""Проверка задания в песочнице: проверочные команды методиста и история команд ученика."""
import logging
from dataclasses import dataclass

from trainer.curriculum.tasks import Check

from .manager import SandboxManager

log = logging.getLogger(__name__)
CHECK_TIMEOUT_S = 10
OUTPUT_LIMIT = 500
HISTORY_FILES = (("lobby", "/home/lobby/.bash_history"), ("student", "/home/student/.bash_history"))
FILES_LIMIT = 80

# Что есть в песочнице (sandbox/image/Dockerfile) — методист пишет это в заданиях, тьютор подсказывает по нему
SANDBOX_NOTE = """Песочница ученика: Debian Linux, bash. Терминал в браузере открывается на входе lobby; на сервер
lab ученик заходит сам: ssh student@lab, там его домашняя папка /home/student (~). На входе lobby команды не
работают — только ssh на сервер (иначе в ответ подсказка «сначала подключись»): вся работа — на lab.
Редакторы файлов: nano (самый простой: сохранить — Ctrl+O и Enter, выйти — Ctrl+X), vim и vi (для тех, кто знает).
Ещё есть: cat, less, echo, ls, tree, mkdir, touch, cp, mv, rm, find, grep, git, python3, node, npm, curl, ssh.
Русские буквы в терминале и в файлах работают (UTF-8). Не у всех есть русская раскладка: такой ученик пишет транслитом
(privet), а проверка ждёт русские слова — в чате задания есть «Транслит → русский»: перевести, скопировать и вставить
в терминал или в nano по Ctrl+V. Сообщения транслитом в чате понимай как обычные."""


def home_files(manager: SandboxManager, student_id: str) -> list[str]:
    """Файлы и папки ученика: ~/… — на сервере lab, /home/lobby/… — на входе (ошибся и создал до ssh)."""
    try:
        r = manager.list_files(student_id)
    except Exception as e:  # noqa: BLE001
        log.warning("список файлов не получен: %s", e)
        return []
    lines = sorted(line.replace("/home/student/", "~/", 1) for line in r.output.splitlines() if line.strip())
    return lines[:FILES_LIMIT] + ([f"… и ещё {len(lines) - FILES_LIMIT}"] if len(lines) > FILES_LIMIT else [])


@dataclass(frozen=True)
class CheckResult:
    cmd: str
    about: str
    passed: bool
    output: str


def run_checks(manager: SandboxManager, student_id: str, checks: list[Check]) -> list[CheckResult]:
    results = []
    for check in checks:
        try:
            r = manager.exec_as_student(student_id, check.cmd, timeout_s=CHECK_TIMEOUT_S)
        except Exception as e:  # noqa: BLE001 — сбой песочницы = проверка не прошла, а не падение хода агента
            log.warning("проверка %r не выполнена: %s", check.cmd, e)
            results.append(CheckResult(check.cmd, check.about, False, "проверку не удалось выполнить"))
            continue
        if r.exit_code in (124, 137):  # timeout / timeout -k
            output = f"(проверка не уложилась в {CHECK_TIMEOUT_S} с)"
        else:
            output = r.output[:OUTPUT_LIMIT]
        results.append(CheckResult(check.cmd, check.about, r.exit_code == 0, output))
    return results


def _parse(user: str, raw: str) -> list[tuple[int, str, str]]:
    out, ts = [], 0
    for line in raw.splitlines():
        if line.startswith("#") and line[1:].isdigit():
            ts = int(line[1:])
        elif line.strip():
            out.append((ts, user, line))
    return out


def history_entries(manager: SandboxManager, student_id: str, limit: int = 40) -> list[tuple[int, str, str]]:
    """Последние команды из обеих оболочек (вход lobby и сервер student) по времени: (unix-время, оболочка, команда)."""
    entries: list[tuple[int, str, str]] = []
    for user, path in HISTORY_FILES:
        try:
            r = manager.read_file(student_id, path)
        except Exception as e:  # noqa: BLE001
            log.warning("история %s не прочитана: %s", path, e)
            continue
        if r.exit_code == 0:
            entries += _parse(user, r.output)
    entries.sort(key=lambda e: e[0])  # sort устойчивый: порядок внутри одной секунды сохраняется
    return entries[-limit:]


def recent_history(manager: SandboxManager, student_id: str, limit: int = 40) -> list[str]:
    return [f"{user}$ {cmd}" for _ts, user, cmd in history_entries(manager, student_id, limit)]


def file_notes(paths: list[str]) -> list[dict]:
    """Пометки для преподавателя: файл на входе lobby (создан до ssh) и имена, отличающиеся только регистром."""
    lowered: dict[str, int] = {}
    for p in paths:
        lowered[p.lower()] = lowered.get(p.lower(), 0) + 1
    out = []
    for p in paths:
        notes = []
        if p.startswith("/home/lobby/"):
            notes.append("на входе lobby, а не на сервере lab")
        if lowered[p.lower()] > 1:
            notes.append("похожее имя рядом — отличается только регистром")
        out.append({"path": p, "note": "; ".join(notes)})
    return out
