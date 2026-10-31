"""Песочницы учеников поверх бэкенда: имена, учебный пароль, пересоздание, команды от имени ученика."""
from sqlalchemy import Engine

from trainer.classroom.groups import GroupStore

from .backend import ExecResult, SandboxBackend, Status, TtySession


def container_name(student_id: str) -> str:
    return f"trainer-sbx-{student_id.replace('-', '')[:12]}"


def volume_name(student_id: str) -> str:
    return f"trainer-home-{student_id.replace('-', '')[:12]}"


class NoSandbox(Exception):
    """Ученик не найден в группе."""


class SandboxManager:
    def __init__(self, backend: SandboxBackend, engine: Engine):
        self._backend, self._engine = backend, engine

    def _student(self, student_id: str):
        student = GroupStore(self._engine).student(student_id)
        if student is None:
            raise NoSandbox(student_id)
        return student

    def ensure_for(self, student_id: str) -> None:
        student = self._student(student_id)
        self._backend.ensure(container_name(student_id), {"LESSON_PASSWORD": student.lesson_password},
                             volume_name(student_id))

    def reset(self, student_id: str) -> None:
        self._student(student_id)
        self._backend.remove(container_name(student_id), volume_name(student_id), wipe=True)
        self.ensure_for(student_id)

    def status(self, student_id: str) -> Status:
        self._student(student_id)
        return self._backend.status(container_name(student_id))

    def exec_as_student(self, student_id: str, cmd: str, timeout_s: int = 10) -> ExecResult:
        self.ensure_for(student_id)
        return self._backend.exec(container_name(student_id), ["bash", "-lc", cmd], user="student",
                                  timeout_s=timeout_s)

    def tty(self, student_id: str) -> TtySession:
        self.ensure_for(student_id)
        return self._backend.attach_tty(container_name(student_id), "lobby")
