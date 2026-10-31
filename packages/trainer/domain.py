import hashlib
import json
from typing import Any

from pydantic import BaseModel, Field


def stable_hash(obj: Any) -> str:
    data = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


class Budget(BaseModel):
    max_input_tokens: int = Field(gt=0)
    max_output_tokens: int = Field(gt=0)
    max_usd: float | None = Field(default=None, gt=0)
    escalation_allowed: bool = False
