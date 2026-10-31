import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from apps.api import agents, auth_local, group, lessons, llm_settings, office, presence, sandbox, tasks, terminal
from trainer.accounts.seed import seed_teacher
from trainer.accounts.store import AccountStore
from trainer.agents.seed import seed_agents
from trainer.agents.store import AgentStore
from trainer.db import get_engine
from trainer.settings import get_settings
from trainer.tutor.jobs import recover_after_restart

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    try:
        engine = get_engine(settings.database_url)
        log.info("преподаватель из env: %s",
                 seed_teacher(AccountStore(engine), settings.teacher_login, settings.teacher_password))
        log.info("агенты по умолчанию: %s", seed_agents(AgentStore(engine)))
        recover_after_restart(engine)
    except Exception:  # API должен подняться и без БД — ошибка видна в логе и в ответах
        log.exception("начальная загрузка не выполнена")
    yield


app = FastAPI(title="Тренажёр юного разработчика", lifespan=lifespan)
app.include_router(auth_local.router)
app.include_router(group.router)
app.include_router(presence.router)
app.include_router(llm_settings.router)
app.include_router(agents.router)
app.include_router(lessons.router)
app.include_router(tasks.router)
app.include_router(sandbox.router)
app.include_router(terminal.router)
app.include_router(office.router)


@app.get("/health")
def health() -> dict:
    return {"ok": True}
