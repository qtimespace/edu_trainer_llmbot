"""Разбор задания для преподавателя: проверки с командами и выводом, файлы ученика с пометками, его команды —
и по кнопке разбор модели «почему не засчитано». Ученику ничего из этого не показывается."""
from datetime import datetime, timezone

from trainer.agents.store import AgentStore
from trainer.curriculum.tasks import Task
from trainer.domain import Budget
from trainer.llm.wiring import build_gateway
from trainer.llm_gateway.gateway import GatewayRequest
from trainer.sandbox.checks import SANDBOX_NOTE, file_notes, history_entries, home_files, run_checks
from trainer.sandbox.manager import SandboxManager

from .jobs import LlmDeps
from .messages import MessageStore

POLICY = "methodist-v1"
ANALYST_PROMPT = """Ты опытный преподаватель-методист в тренажёре юного разработчика (ученикам 13+). Коллега-преподаватель
просит разобрать, почему задание ученика не засчитано. Тебе даны задание, проверочные команды с результатом,
файлы и папки ученика, его команды в терминале и переписка с агентом-тьютором.

Ответь преподавателю коротко, по-русски, простым текстом (без JSON):
1. Что не так — по каждой непройденной проверке: что она ждёт и что у ученика на самом деле.
2. Где ученик ошибся — по его командам (опечатка, регистр, не та папка, создал на входе lobby до ssh, лишние попытки
   рядом, не тот редактор и т. п.).
3. Что подсказать ученику — 1–2 наводящие фразы, без готовой команды-решения.
Если все проверки прошли — так и скажи и предложи, что спросить на понимание. Если проверка сама написана неудачно
(слишком строгая, ловит не то) — скажи об этом преподавателю прямо."""


def inspect(manager: SandboxManager, task: Task) -> dict:
    results = run_checks(manager, task.student_id, task.checks)
    return {"checks": [{"about": r.about, "cmd": r.cmd, "passed": r.passed, "output": r.output} for r in results],
            "files": file_notes(home_files(manager, task.student_id))}


def console(manager: SandboxManager, student_id: str, limit: int = 300) -> list[dict]:
    return [{"at": ts, "where": user, "cmd": cmd} for ts, user, cmd in history_entries(manager, student_id, limit)]


def _when(ts: int) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%H:%M:%S") if ts else "--:--:--"


def analyze(deps: LlmDeps, manager: SandboxManager, task: Task) -> dict:
    """Разбор модели для преподавателя; платит ключ преподавателя, бюджет ученика не трогаем (student_id=None)."""
    agent = next(iter(AgentStore(deps.engine).list(kind="methodist", enabled_only=True)), None)
    if agent is None:
        raise ValueError("нужен включённый методист — он делает разбор")
    seen = inspect(manager, task)
    checks = "\n".join(f"{'✓' if c['passed'] else '✗'} {c['about']}\n   команда: {c['cmd']}"
                       + (f"\n   вывод: {c['output'].strip()[:300]}" if c["output"].strip() else "")
                       for c in seen["checks"])
    files = "\n".join(f["path"] + (f"  ← {f['note']}" if f["note"] else "") for f in seen["files"])
    history = "\n".join(f"{_when(e['at'])} {e['where']}$ {e['cmd'][:300]}" for e in console(manager, task.student_id, 80))
    talk = "\n".join(f"{'Ученик' if m.author == 'student' else 'Агент' if m.author == 'agent' else 'Система'}: "
                     f"{m.text[:800]}" for m in MessageStore(deps.engine).for_task(task.id)[-20:])
    user = (f"{SANDBOX_NOTE}\n\nЗадание: {task.title}\n{task.statement}\n\n"
            f"Проверки сейчас:\n{checks or '(проверок нет)'}\n\n"
            f"Файлы и папки ученика (~ — сервер lab, /home/lobby — вход), без скрытых:\n{files or '(пусто)'}\n\n"
            f"Команды ученика в терминале (время UTC):\n{history or '(команд нет)'}\n\n"
            f"Переписка по заданию:\n{talk or '(не было)'}")
    resp = build_gateway(deps.engine, deps.settings, student_id=None, providers=deps.providers).execute(
        GatewayRequest(task_id=task.id, agent=agent.key, policy=POLICY, capabilities=[], system=ANALYST_PROMPT,
                       user=user, budget=Budget(max_input_tokens=32000, max_output_tokens=1500,
                                                max_usd=agent.max_usd_per_call),
                       route=agent.route or None))
    return {"text": resp.text.strip(), "model": resp.model_key, "cost_usd": resp.cost_usd}
