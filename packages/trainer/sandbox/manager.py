"""Песочницы учеников поверх бэкенда: имена, учебный пароль, пересоздание, команды от имени ученика."""
from sqlalchemy import Engine

from trainer.classroom.groups import GroupStore

from .backend import ExecResult, SandboxBackend, Status, TtySession


CLEAN_ENV = ["env", "-i", "HOME=/home/student", "USER=student", "LANG=C.UTF-8",
             "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"]


def container_name(student_id: str) -> str:
    return f"trainer-sbx-{student_id.replace('-', '')[:12]}"


def volume_name(seat: int) -> str:
    """Том /home места в группе: создаётся заранее с ограничением размера (deploy.sh), при пересоздании — очищается."""
    return f"trainer-home-seat{seat}"


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
                             volume_name(student.seat))

    def reset(self, student_id: str) -> None:
        student = self._student(student_id)
        self._backend.remove(container_name(student_id), volume_name(student.seat), wipe=True)
        self.ensure_for(student_id)

    def status(self, student_id: str) -> Status:
        self._student(student_id)
        return self._backend.status(container_name(student_id))

    def exec_as_student(self, student_id: str, cmd: str, timeout_s: int = 10) -> ExecResult:
        self.ensure_for(student_id)
        # чистое окружение и без ~/.bashrc/.profile: ученик не подменит test/grep алиасом и не «пройдёт» проверку
        return self._backend.exec(container_name(student_id), CLEAN_ENV + ["bash", "--noprofile", "--norc", "-c", cmd],
                                  user="student", timeout_s=timeout_s)

    def read_file(self, student_id: str, path: str) -> ExecResult:
        """Файл песочницы от root (история обеих оболочек); песочницу не поднимает — нет её, нет и файла."""
        return self._backend.exec(container_name(student_id), ["tail", "-c", "65536", path], user="root", timeout_s=5)

    def tty(self, student_id: str) -> TtySession:
        self.ensure_for(student_id)
        return self._backend.attach_tty(container_name(student_id), "lobby")
