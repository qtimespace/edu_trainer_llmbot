"""Ход агента-тьютора: проверки в песочнице + история команд + переписка → ответ модели (JSON) → статус.

Задание закрывается (done) тогда и только тогда, когда прошли ВСЕ проверочные команды; `done` модели — подсказка.
"""
import logging

from pydantic import BaseModel, Field, ValidationError

from trainer.agents.store import AgentStore
from trainer.classroom.groups import GroupStore
from trainer.curriculum.methodist import extract_json
from trainer.curriculum.tasks import TaskStore
from trainer.domain import Budget
from trainer.llm.wiring import build_gateway, remaining_usd
from trainer.llm_gateway.gateway import GatewayError, GatewayRequest
from trainer.sandbox.checks import CheckResult, recent_history, run_checks
from trainer.sandbox.manager import SandboxManager

from .jobs import JobStore, LlmDeps
from .messages import MessageStore

log = logging.getLogger(__name__)
POLICY = "tutor-v1"
SOFT_ERROR = "Агент сейчас не смог ответить — попробуй ещё раз через минуту."
NO_BUDGET = "Лимит расходов на агентов исчерпан — позови преподавателя."
KEY_PROBLEM = "У преподавателя закончился баланс или не работает ключ модели — позови преподавателя."
MIN_TURN_USD = 0.002  # меньше — ход всё равно не поместится в остаток: не обещаем «попробуй ещё раз»
HISTORY_LINE, HISTORY_TOTAL, MESSAGE_CHARS = 300, 6000, 1500
_REASON_TEXT = {"budget_exceeded": NO_BUDGET, "quota_exceeded": KEY_PROBLEM, "auth": KEY_PROBLEM}


class TutorReply(BaseModel):
    reply: str = Field(min_length=1, max_length=4000)
    done: bool = False


def _cut(text_: str, limit: int) -> str:
    return text_ if len(text_) <= limit else text_[:limit] + "…"


def _recent(history: list[str]) -> list[str]:
    """Свежие команды важнее; длинная вставка не переполняет запрос модели."""
    out, size = [], 0
    for line in reversed(history):
        line = _cut(line, HISTORY_LINE)
        if size + len(line) > HISTORY_TOTAL:
            break
        out.insert(0, line)
        size += len(line)
    return out


def _reason(e: Exception) -> str:
    """Причина неудачи хода: по ней ученику — понятный текст, преподавателю — в ленту."""
    if not isinstance(e, GatewayError):
        return "bad_reply"
    if e.reason != "exhausted":
        return e.reason
    if any(a.outcome == "skipped_budget" for a in e.attempts):
        return "budget_exceeded"
    kinds = {a.error_kind for a in e.attempts}
    return next((k for k in ("quota_exceeded", "auth") if k in kinds), e.reason)


def _prompt(task, results: list[CheckResult], history: list[str], messages) -> str:
    checks = "\n".join(f"{'✓' if r.passed else '✗'} {r.about}" + (f" — вывод: {r.output.strip()[:200]}"
                                                                   if r.output.strip() and not r.passed else "")
                       for r in results)
    talk = "\n".join(f"{'Ученик' if m.author == 'student' else 'Ты' if m.author == 'agent' else 'Система'}: "
                     f"{_cut(m.text, MESSAGE_CHARS)}" for m in messages[-20:]) or "(пока не было — начни разговор)"
    history = _recent(history)
    return (f"Задание ученика: {task.title}\n{task.statement}\n\n"
            f"Результаты проверок в его песочнице (✓ — выполнено, ✗ — нет):\n{checks or '(проверок нет)'}\n\n"
            f"Последние команды ученика (lobby$ — вход, student$ — сервер lab):\n"
            f"{chr(10).join(history) or '(команд пока нет)'}\n\n"
            f"Переписка:\n{talk}")


def tutor_turn(deps: LlmDeps, manager: SandboxManager, task_id: str, student_id: str, job_id: str) -> None:
    """Один ход агента. Задание уже в статусе in_progress, ход уже зарегистрирован в agent_jobs (job_id)."""
    engine = deps.engine
    tasks, messages = TaskStore(engine), MessageStore(engine)
    ok = False
    try:
        task = tasks.get(task_id)
        student = GroupStore(engine).student(student_id)
        agent = AgentStore(engine).get(task.agent_key)
        left = remaining_usd(engine, student_id, student.budget_usd)
        if left < MIN_TURN_USD:
            messages.add(task_id, "system", NO_BUDGET)
            tasks.set_status(task_id, "waiting_student")
            ok = True
            return
        results = run_checks(manager, student_id, task.checks)
        history = recent_history(manager, student_id)
        if not JobStore(engine).owns(job_id):  # пока шли проверки, ход признали зависшим — деньги не тратим
            log.warning("ход по заданию %s отобран как зависший — вызов модели пропущен", task_id)
            return
        try:
            resp = build_gateway(engine, deps.settings, student_id=student_id, providers=deps.providers).execute(
                GatewayRequest(task_id=task_id, agent=agent.key, policy=POLICY, capabilities=[],
                               system=agent.system_prompt, user=_prompt(task, results, history, messages.for_task(task_id)),
                               budget=Budget(max_input_tokens=32000, max_output_tokens=1500,
                                             max_usd=min(agent.max_usd_per_call, left)),
                               route=agent.route or None))
            answer = TutorReply.model_validate(extract_json(resp.text))
        except (GatewayError, ValueError, ValidationError) as e:
            reason = _reason(e)
            log.warning("ход %s по заданию %s не удался: %s", agent.key, task_id, reason)
            messages.add(task_id, "system", _REASON_TEXT.get(reason, SOFT_ERROR), meta={"reason": reason})
            tasks.set_status(task_id, "waiting_student")
            return
        passed = bool(results) and all(r.passed for r in results)
        messages.add(task_id, "agent", answer.reply, agent_key=agent.key,
                     meta={"checks": [r.__dict__ for r in results], "model": resp.model_key,
                           "cost_usd": resp.cost_usd, "model_done": answer.done})
        tasks.set_status(task_id, "done" if passed else "waiting_student")
        ok = True
    except Exception:
        log.exception("ход агента по заданию %s упал", task_id)
        try:
            messages.add(task_id, "system", SOFT_ERROR)
            tasks.set_status(task_id, "waiting_student")
        except Exception:  # noqa: BLE001
            pass
    finally:
        JobStore(engine).finish(job_id, ok)
