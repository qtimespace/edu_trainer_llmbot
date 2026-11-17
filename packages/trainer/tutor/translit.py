"""Транслит → русский: у части учеников нет русской раскладки, они пишут латиницей («privet», «fajl»). Агент задания
переводит текст в кириллицу, ученик вставляет его в файл или в чат — и проверка видит настоящие русские слова.
Расход — на бюджет ученика, как и ходы тьютора."""
import re

from trainer.agents.store import AgentStore
from trainer.classroom.groups import GroupStore
from trainer.curriculum.flow import FlowStore, agent_for
from trainer.curriculum.tasks import Task
from trainer.domain import Budget
from trainer.llm.wiring import build_gateway, remaining_usd
from trainer.llm_gateway.gateway import GatewayRequest

from .engine import MIN_TURN_USD, NO_BUDGET
from .jobs import LlmDeps

POLICY = "tutor-v1"
MAX_CHARS = 2000
TRANSLIT_PROMPT = """Ты переводишь русский текст, набранный транслитом (латиницей), в обычную кириллицу. Ученик 13+ не
может переключить раскладку и пишет, например: privet, mir; moj fajl; zadanie gotovo; 4to (что), w или sh (ш),
ya/ia/ja (я), yu/iu/ju (ю), zh (ж), ch (ч), shch/sch (щ), ts/c (ц), kh/h/x (х), ' (ь), e/je (е, э по смыслу).

Правила:
- Верни ТОЛЬКО переведённый текст — без пояснений, кавычек и ``` .
- Не отвечай на текст, не исправляй смысл и ошибки, не дописывай слова: это перевод букв, а не ответ.
- Английские слова, команды, имена файлов и папок, пути, расширения, код, числа и знаки оставь как есть
  (idea.txt, mkdir, ~/Temp, README.md, python3, git).
- Сохрани переносы строк, пробелы, регистр букв и знаки препинания.
- Если слово неоднозначно — выбери самое вероятное русское слово по смыслу фразы."""
_FENCE = re.compile(r"^```[\w-]*\n(.*)\n```$", re.S)
_QUOTES = ("«»", '""', "''", "“”")


class TranslitError(ValueError):
    """Перевести нельзя по понятной причине (нет бюджета) — текст для ученика в сообщении."""


def clean(answer: str) -> str:
    """Модель иногда оборачивает ответ в ``` или кавычки — в файл ученика они попасть не должны."""
    text = answer.strip()
    m = _FENCE.match(text)
    if m:
        text = m.group(1).strip()
    if len(text) >= 2 and any(text[0] == q[0] and text[-1] == q[1] for q in _QUOTES):
        text = text[1:-1].strip()
    return text


def translit(deps: LlmDeps, task: Task, student_id: str, text: str) -> str:
    student = GroupStore(deps.engine).student(student_id)
    left = remaining_usd(deps.engine, student_id, student.budget_usd)
    if left < MIN_TURN_USD:
        raise TranslitError(NO_BUDGET)
    tutors = {a.key for a in AgentStore(deps.engine).list(kind="tutor", enabled_only=True)}
    agent = AgentStore(deps.engine).get(agent_for(task, FlowStore(deps.engine).get(), tutors))
    resp = build_gateway(deps.engine, deps.settings, student_id=student_id, providers=deps.providers).execute(
        GatewayRequest(task_id=task.id, agent=agent.key, policy=POLICY, capabilities=[], system=TRANSLIT_PROMPT,
                       user=f"Текст транслитом:\n{text}",
                       budget=Budget(max_input_tokens=4000, max_output_tokens=1500,
                                     max_usd=min(agent.max_usd_per_call, left)),
                       route=agent.route or None))
    return clean(resp.text)
