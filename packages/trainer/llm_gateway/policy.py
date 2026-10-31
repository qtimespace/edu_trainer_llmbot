from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

from trainer.domain import stable_hash

from .errors import ErrorKind


class Constraints(BaseModel):
    max_cost_usd: float = Field(gt=0)
    max_input_tokens: int = Field(gt=0)
    max_output_tokens: int = Field(gt=0)
    max_attempts: int = Field(ge=1)


class FallbackRules(BaseModel):
    on: list[ErrorKind]
    strategy: list[Literal["next_model", "cheaper_model"]]


class Quality(BaseModel):
    min_confidence: float = Field(ge=0, le=1)


class RunLimits(BaseModel):
    max_audits: int = Field(ge=0)
    max_cost_usd: float = Field(ge=0)


class Policy(BaseModel):
    name: str
    version: int = 1
    execution: Literal["single", "fallback"] = "fallback"
    constraints: Constraints
    preferred: list[str]
    fallback: FallbackRules
    quality: Quality
    run_limits: RunLimits | None = None

    @property
    def hash(self) -> str:
        return stable_hash(self.model_dump(mode="json"))


def load_policy(path: Path | str) -> Policy:
    return Policy(**yaml.safe_load(Path(path).read_text(encoding="utf-8"))["policy"])


def load_policies(directory: Path | str) -> dict[str, Policy]:
    policies = [load_policy(p) for p in sorted(Path(directory).glob("*.yaml"))]
    return {p.name: p for p in policies}
