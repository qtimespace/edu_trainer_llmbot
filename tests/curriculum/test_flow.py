import pytest
from pydantic import ValidationError

from trainer.curriculum.flow import DEFAULT_FLOW, Flow, FlowStore, Stage, agent_for, stage_of
from trainer.curriculum.tasks import Task


def _flow(stages, transitions):
    return Flow(stages=[Stage(key=k, name=k, agent_key=a) for k, a in stages], transitions=transitions)


def _task(status="todo", stage=None, agent_key="devops"):
    return Task(id="t", lesson_id="l", student_id="s", agent_key=agent_key, title="", statement="", status=status,
                position=1, stage=stage)


def test_default_flow_is_analysis_development_review():
    assert [s.key for s in DEFAULT_FLOW.stages] == ["todo", "analysis", "dev", "review", "done"]
    assert ("review", "done") in DEFAULT_FLOW.moves() and ("review", "dev") in DEFAULT_FLOW.moves()
    assert DEFAULT_FLOW.first_work_stage() == "analysis"


@pytest.mark.parametrize("stages, transitions, why", [
    ([("todo", None), ("dev", None)], [("todo", "dev")], "done"),               # нет «Готово»
    ([("todo", None), ("dev", None), ("dev", None), ("done", None)], [("todo", "dev"), ("dev", "done")], "повтор"),
    ([("todo", None), ("dev", None), ("done", None)], [("todo", "dev"), ("dev", "x"), ("dev", "done")], "x"),
    ([("todo", None), ("dev", None), ("done", None)], [("todo", "dev"), ("dev", "todo"), ("dev", "done")], "todo"),
    ([("todo", None), ("dev", None), ("done", None)], [("todo", "dev"), ("done", "dev"), ("dev", "done")], "done"),
    ([("todo", None), ("dev", None), ("done", None)], [("todo", "dev")], "done"),  # в «Готово» не попасть
    ([("todo", None), ("a", None), ("b", None), ("done", None)], [("todo", "a"), ("a", "done")], "b"),  # b недостижим
])
def test_broken_flow_is_rejected(stages, transitions, why):
    with pytest.raises(ValidationError) as e:
        _flow(stages, transitions)
    assert why in str(e.value)


def test_stage_of_task_falls_back_to_status():
    assert stage_of(_task("todo"), DEFAULT_FLOW) == "todo"
    assert stage_of(_task("done", stage="review"), DEFAULT_FLOW) == "done"
    assert stage_of(_task("waiting_student"), DEFAULT_FLOW) == "analysis"
    assert stage_of(_task("in_progress", stage="review"), DEFAULT_FLOW) == "review"
    assert stage_of(_task("in_progress", stage="removed"), DEFAULT_FLOW) == "analysis"  # этап убрали из флоу


def test_agent_of_the_stage_leads_the_task():
    tutors = {"devops", "sa", "techlead"}
    assert agent_for(_task("in_progress", stage="analysis"), DEFAULT_FLOW, tutors) == "sa"
    assert agent_for(_task("in_progress", stage="dev"), DEFAULT_FLOW, tutors) == "devops"  # агент задания
    assert agent_for(_task("in_progress", stage="review"), DEFAULT_FLOW, {"devops"}) == "devops"  # техлид выключен


def test_store_keeps_teachers_flow(engine):
    store = FlowStore(engine)
    assert store.get() == DEFAULT_FLOW
    mine = _flow([("todo", None), ("dev", "python"), ("done", None)], [("todo", "dev"), ("dev", "done")])
    store.save(mine)
    assert store.get() == mine
