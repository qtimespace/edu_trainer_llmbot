"""Методист: по описанию урока и заметке об ученике готовит индивидуальные черновики заданий."""
import json
import logging

from pydantic import BaseModel, Field, ValidationError

from trainer.agents.store import AgentStore
from trainer.classroom.groups import GroupStore, Student
from trainer.curriculum.lessons import Lesson, LessonStore
from trainer.curriculum.tasks import Check, TaskStore
from trainer.domain import Budget
from trainer.llm.wiring import build_gateway
from trainer.llm_gateway.gateway import GatewayError, GatewayRequest
from trainer.tutor.jobs import JobStore, LlmDeps

log = logging.getLogger(__name__)
POLICY = "methodist-v1"


class DraftTask(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    statement: str = Field(min_length=1, max_length=5000)
    agent_key: str = ""
    checks: list[Check] = Field(min_length=1, max_length=8)


class MethodistOutput(BaseModel):
    tasks: list[DraftTask] = Field(min_length=1, max_length=10)


def extract_json(raw: str) -> dict:
    """JSON-объект из ответа модели (допускаются ```-блок и текст вокруг)."""
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("в ответе нет JSON")
    return json.loads(raw[start:end + 1])


def _prompt(lesson: Lesson, student: Student, tutors: list[dict]) -> str:
    return (f"Урок: {lesson.title}\n\nОписание урока от преподавателя:\n{lesson.description}\n\n"
            f"Ученик: {student.name}\nЗаметка преподавателя об ученике: {student.note or '(нет)'}\n\n"
            f"Агенты-тьюторы (agent_key → имя): {json.dumps(tutors, ensure_ascii=False)}")


def _prepare_one(deps: LlmDeps, lesson: Lesson, student: Student) -> None:
    agents = AgentStore(deps.engine)
    methodist = next(iter(agents.list(kind="methodist", enabled_only=True)), None)
    tutors = agents.list(kind="tutor", enabled_only=True)
    if methodist is None or not tutors:
        raise ValueError("нужен включённый методист и хотя бы один тьютор")
    gateway = build_gateway(deps.engine, deps.settings, student_id=None, providers=deps.providers)
    job = JobStore(deps.engine).start(methodist.key, lesson_id=lesson.id, student_id=student.account_id)
    ok = False
    try:
        resp = gateway.execute(GatewayRequest(
            task_id=f"lesson:{lesson.id}", agent=methodist.key, policy=POLICY, capabilities=[],
            system=methodist.system_prompt, user=_prompt(lesson, student, [{"key": t.key, "name": t.name} for t in tutors]),
            budget=Budget(max_input_tokens=32000, max_output_tokens=8000, max_usd=methodist.max_usd_per_call),
            route=methodist.route or None))
        out = MethodistOutput.model_validate(extract_json(resp.text))
        keys = {t.key for t in tutors}
        drafts = [{"title": t.title, "statement": t.statement, "checks": t.checks,
                   "agent_key": t.agent_key if t.agent_key in keys else tutors[0].key} for t in out.tasks]
        TaskStore(deps.engine).replace_drafts(lesson.id, student.account_id, drafts)
        ok = True
    finally:
        if job:
            JobStore(deps.engine).finish(job, ok)


def prepare_lesson(deps: LlmDeps, lesson_id: str, student_id: str | None = None) -> None:
    """Подготовка заданий (lesson.prep_status уже 'running'). Ошибка по ученику не мешает остальным."""
    lessons = LessonStore(deps.engine)
    lesson = lessons.get(lesson_id)
    students = [s for s in GroupStore(deps.engine).students() if student_id is None or s.account_id == student_id]
    errors = []
    for student in students:
        try:
            _prepare_one(deps, lesson, student)
        except GatewayError as e:
            errors.append(f"{student.login}: модель не ответила ({e.reason})")
        except (ValueError, ValidationError) as e:
            errors.append(f"{student.login}: ответ методиста не разобран ({str(e)[:200]})")
        except Exception as e:  # noqa: BLE001 — урок не должен навсегда остаться в running
            log.exception("подготовка урока %s для %s", lesson_id, student.login)
            errors.append(f"{student.login}: {type(e).__name__}")
    lessons.set_prep(lesson_id, "failed" if errors else "idle", "\n".join(errors))
