"""Учётные записи тренажёра: преподаватель и ученики."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

Role = Literal["teacher", "student"]


class Account(BaseModel):
    id: str
    login: str
    name: str = ""
    role: Role
    active: bool = True
    must_change_password: bool = False
    created_at: datetime | None = None
