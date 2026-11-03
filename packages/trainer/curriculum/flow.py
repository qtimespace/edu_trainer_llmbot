"""Флоу заданий: этапы доски по порядку и разрешённые переходы. Ведёт преподаватель; у этапа — свой агент.

Первый этап `todo` и последний `done` постоянные. В `done` задание попадает только когда прошли все проверки.
"""
import json

from pydantic import BaseModel, Field, model_validator
from sqlalchemy import Engine, text

START, DONE = "todo", "done"


class Stage(BaseModel):
    key: str = Field(pattern=r"^[a-z0-9_-]{1,32}$")
    name: str = Field(min_length=1, max_length=40)
    agent_key: str | None = None  # None — агент задания (его выбрал методист)


class Flow(BaseModel):
    stages: list[Stage]
    transitions: list[tuple[str, str]]

    @model_validator(mode="after")
    def _valid(self) -> "Flow":
        keys = [s.key for s in self.stages]
        if len(set(keys)) != len(keys):
            raise ValueError("повтор ключа этапа")
        if len(keys) < 3 or keys[0] != START or keys[-1] != DONE:
            raise ValueError(f"первый этап — {START}, последний — {DONE}, между ними хотя бы один")
        for a, b in self.transitions:
            if a not in keys or b not in keys:
                raise ValueError(f"переход {a} → {b}: нет такого этапа")
            if b == START:
                raise ValueError(f"в этап {START} переходов нет")
            if a == DONE:
                raise ValueError(f"из этапа {DONE} переходов нет")
        reached, edge = {START}, True
        while edge:
            edge = False
            for a, b in self.transitions:
                if a in reached and b not in reached:
                    reached.add(b)
                    edge = True
        lost = [k for k in keys if k not in reached]
        if lost:
            raise ValueError(f"этапы недостижимы из {START}: {', '.join(lost)}" + (" (в done не попасть)" if DONE in lost else ""))
        return self

    def moves(self) -> set[tuple[str, str]]:
        return {(a, b) for a, b in self.transitions}

    def stage(self, key: str) -> Stage | None:
        return next((s for s in self.stages if s.key == key), None)

    def first_work_stage(self) -> str:
        return next((b for a, b in self.transitions if a == START and b != DONE), self.stages[1].key)


DEFAULT_FLOW = Flow(stages=[Stage(key=START, name="К выполнению"), Stage(key="analysis", name="Анализ", agent_key="sa"),
                            Stage(key="dev", name="Разработка"), Stage(key="review", name="Ревью", agent_key="techlead"),
                            Stage(key=DONE, name="Готово")],
                    transitions=[(START, "analysis"), ("analysis", "dev"), ("dev", "review"), ("review", DONE),
                                 ("review", "dev"), ("dev", "analysis")])


def stage_of(task, flow: Flow) -> str:
    """Этап задания на доске; без этапа (или этап убрали из флоу) — по статусу."""
    if task.status == "done":
        return DONE
    if task.status == "todo":
        return START
    return task.stage if task.stage and task.stage not in (START, DONE) and flow.stage(task.stage) else flow.first_work_stage()


def agent_for(task, flow: Flow, tutors: set[str]) -> str:
    """Кто ведёт задание сейчас: агент этапа (если включён), иначе агент задания."""
    stage = flow.stage(stage_of(task, flow))
    return stage.agent_key if stage and stage.agent_key in tutors else task.agent_key


class FlowStore:
    def __init__(self, engine: Engine):
        self._engine = engine

    def get(self) -> Flow:
        with self._engine.connect() as c:
            doc = c.execute(text("SELECT document FROM flow WHERE id = 1")).scalar()
        return Flow.model_validate(doc) if doc else DEFAULT_FLOW

    def save(self, flow: Flow) -> Flow:
        with self._engine.begin() as c:
            c.execute(text("""INSERT INTO flow (id, document) VALUES (1, CAST(:d AS jsonb))
                              ON CONFLICT (id) DO UPDATE SET document = EXCLUDED.document, updated_at = now()"""),
                      {"d": json.dumps(flow.model_dump(), ensure_ascii=False)})
        return flow
