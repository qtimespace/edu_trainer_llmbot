from trainer.agents.seed import seed_agents
from trainer.agents.store import AgentStore
from trainer.classroom.groups import GroupStore
from trainer.curriculum.lessons import LessonStore
from trainer.tutor.jobs import JobStore, recover_after_restart


def test_recover_after_restart_closes_running_work(engine):
    seed_agents(AgentStore(engine))
    GroupStore(engine).create("g", 2)
    lesson = LessonStore(engine).create("Bash", "")
    LessonStore(engine).set_prep(lesson.id, "running")
    jobs = JobStore(engine)
    jobs.start("methodist", lesson_id=lesson.id)
    recover_after_restart(engine)
    assert jobs.running() == []
    got = LessonStore(engine).get(lesson.id)
    assert got.prep_status == "failed" and "перезапуск" in got.prep_error
