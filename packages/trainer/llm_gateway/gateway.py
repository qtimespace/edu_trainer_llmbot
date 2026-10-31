import uuid
from typing import Literal

from pydantic import BaseModel

from trainer.domain import Budget

from .budget import BudgetTracker, estimate_tokens
from .errors import ProviderError
from .health import CircuitBreaker
from .ledger import InMemoryLedger, Ledger, LedgerEntry
from .limits import LimitGuard
from .policy import Policy
from .providers.base import Provider, ProviderRequest
from .registry import ModelRegistry, ModelSpec, model_source

# auth/quota_exceeded — свойство ключа пользователя, не провайдера: не выключаем провайдера всем
_BREAKER_KINDS = {"timeout", "provider_error", "rate_limit"}


class GatewayRequest(BaseModel):
    task_id: str
    agent: str
    policy: str
    capabilities: list[str]
    system: str
    user: str
    budget: Budget
    # профиль агента: точный порядок моделей (ключи реестра); None — выборка по capabilities
    route: list[str] | None = None
    # провайдеры, которым нельзя отвечать (независимая проверка, спека 3.I §6)
    exclude_providers: list[str] = []


class AttemptRecord(BaseModel):
    model_key: str
    outcome: Literal["ok", "error", "skipped_budget", "skipped_limit"]
    error_kind: str | None = None


class GatewayResponse(BaseModel):
    text: str
    model_key: str
    model: str
    provider: str
    source: str = ""  # производитель модели (registry.model_source) — по нему считается независимость
    input_tokens: int
    output_tokens: int
    cost_usd: float
    attempts: list[AttemptRecord]
    # неудачные попытки с расходом (обрезанный ответ и т. п.) — деньги потрачены, хотя ответа нет
    failed_cost_usd: float = 0.0


class GatewayError(Exception):
    def __init__(self, reason: str, attempts: list[AttemptRecord], cost_usd: float = 0.0,
                 tokens: tuple[int, int] | None = None, retry_at: float | None = None):
        super().__init__(reason)
        self.reason = reason
        self.attempts = attempts
        self.cost_usd = cost_usd
        self.tokens = tokens  # context_overflow: (оценка входа, лимит входа)
        self.retry_at = retry_at  # rate_limited: когда снимется ближайшая пауза (unix-время)


class LLMGateway:
    def __init__(self, registry: ModelRegistry, policies: dict[str, Policy], providers: dict[str, Provider],
                 breaker: CircuitBreaker | None = None, ledger: Ledger | None = None,
                 limits: LimitGuard | None = None):
        self._registry = registry
        self._policies = policies
        self._providers = providers
        self._breaker = breaker or CircuitBreaker()
        self._ledger = ledger or InMemoryLedger()
        self._limits = limits

    def execute(self, req: GatewayRequest) -> GatewayResponse:
        policy = self._policies.get(req.policy)
        if policy is None:
            raise GatewayError("unknown_policy", [])
        c = policy.constraints
        max_in = min(c.max_input_tokens, req.budget.max_input_tokens)
        max_out = min(c.max_output_tokens, req.budget.max_output_tokens)
        max_usd = min(c.max_cost_usd, req.budget.max_usd) if req.budget.max_usd else c.max_cost_usd
        est_in = estimate_tokens(req.system) + estimate_tokens(req.user)
        if est_in > max_in:
            raise GatewayError("context_overflow", [], tokens=(est_in, max_in))

        if req.route is not None:
            enabled = {m.key: m for m in self._registry.enabled}
            pool = [enabled[k] for k in req.route if k in enabled]
        else:
            pool = self._registry.candidates(req.capabilities or policy.preferred)
        # исключаются источники (производители), а не провайдеры: deepseek и qwen на одном hf — независимы
        excluded = set(req.exclude_providers)
        candidates = [m for m in pool if m.provider in self._providers and model_source(m) not in excluded
                      and m.context_window >= est_in + max_out]
        if policy.execution == "single":
            candidates = candidates[:1]

        tracker = BudgetTracker(max_usd)
        attempts: list[AttemptRecord] = []
        skip_providers: set[str] = set()
        calls = 0
        failed_cost = 0.0
        for round_ in range(2):  # второй круг — только после короткого ожидания снятия паузы (лимиты)
            waits: list[float] = []
            for spec in candidates:
                if spec.provider in skip_providers or not self._breaker.allow(spec.provider):
                    continue
                if self._limits is not None:
                    blocked = self._limits.blocked(spec, est_in + max_out)
                    if blocked is not None:  # пауза или лимит не выдержит запрос — следующая модель маршрута
                        attempts.append(AttemptRecord(model_key=spec.key, outcome="skipped_limit",
                                                      error_kind=blocked[1]))
                        if blocked[0] is not None:  # None — запрос больше самого лимита: ждать нечего
                            waits.append(blocked[0])
                        continue
                done = self._try(req, policy, spec, c, est_in, max_out, tracker, attempts, skip_providers, calls,
                                 failed_cost)
                calls, failed_cost = done[1], done[2]
                if done[0] is not None:
                    return done[0]
            limited = attempts and all(a.outcome == "skipped_limit" for a in attempts)
            if not limited or round_ == 1:
                break
            if not waits or not self._limits.wait_until(min(waits)):
                raise GatewayError("rate_limited", attempts, failed_cost, retry_at=min(waits) if waits else None)
            attempts.clear()
        if attempts and all(a.outcome == "skipped_limit" for a in attempts):
            raise GatewayError("rate_limited", attempts, failed_cost, retry_at=min(waits) if waits else None)
        raise GatewayError("exhausted" if attempts else "no_candidates", attempts, failed_cost)

    def _try(self, req: GatewayRequest, policy: Policy, spec: ModelSpec, c, est_in: int, max_out: int,
             tracker: BudgetTracker, attempts: list[AttemptRecord], skip_providers: set[str], calls: int,
             failed_cost: float) -> tuple[GatewayResponse | None, int, float]:
        """Вызовы одной модели (повтор по таймауту). → (ответ или None, вызовов, расход неудач)."""
        timeout_retries = 1
        while True:
            if calls >= c.max_attempts:
                raise GatewayError("max_attempts", attempts, failed_cost)
            estimate = spec.cost_usd(est_in, max_out)
            if not tracker.reserve(estimate):
                attempts.append(AttemptRecord(model_key=spec.key, outcome="skipped_budget"))
                if "cheaper_model" not in policy.fallback.strategy:
                    raise GatewayError("budget_exceeded", attempts, failed_cost)
                return None, calls, failed_cost
            calls += 1
            try:
                resp = self._providers[spec.provider].complete(ProviderRequest(
                    model=spec.model, system=req.system, user=req.user, max_output_tokens=max_out,
                    server_side_fallback=spec.server_side_fallback, effort=spec.effort,
                    max_tokens_param=spec.max_tokens_param, thinking=spec.thinking,
                ))
            except ProviderError as e:
                actual = spec.cost_usd(*e.usage) if e.usage else 0.0
                failed_cost += actual
                tracker.settle(estimate, actual)
                if e.usage:
                    self._record(req, spec, spec.model, e.usage[0], e.usage[1], actual)
                attempts.append(AttemptRecord(model_key=spec.key, outcome="error", error_kind=e.kind))
                if e.kind in _BREAKER_KINDS:
                    self._breaker.record_failure(spec.provider)
                if self._limits is not None:  # 429/квота — пауза на всех процессах, не только в этом вызове
                    self._limits.on_error(spec, e.kind, e.retry_after)
                if e.kind not in policy.fallback.on:
                    raise GatewayError(e.kind, attempts, failed_cost) from e
                if e.kind == "timeout" and timeout_retries > 0:
                    timeout_retries -= 1
                    continue
                if e.kind == "rate_limit":
                    skip_providers.add(spec.provider)
                return None, calls, failed_cost
            cost = spec.cost_usd(resp.input_tokens, resp.output_tokens)
            tracker.settle(estimate, cost)
            self._breaker.record_success(spec.provider)
            if self._limits is not None:
                self._limits.on_success(spec, resp.input_tokens + resp.output_tokens)
            self._record(req, spec, resp.model, resp.input_tokens, resp.output_tokens, cost)
            attempts.append(AttemptRecord(model_key=spec.key, outcome="ok"))
            return GatewayResponse(text=resp.text, model_key=spec.key, model=resp.model,
                                   provider=spec.provider, source=model_source(spec), input_tokens=resp.input_tokens,
                                   output_tokens=resp.output_tokens, cost_usd=cost, attempts=attempts,
                                   failed_cost_usd=failed_cost), calls, failed_cost

    def _record(self, req: GatewayRequest, spec: ModelSpec, model: str, tokens_in: int, tokens_out: int,
                cost: float) -> None:
        self._ledger.record(LedgerEntry(
            request_id=uuid.uuid4().hex, provider=spec.provider, model=model, model_key=spec.key,
            input_tokens=tokens_in,
            output_tokens=tokens_out, cost_usd=cost, agent=req.agent, task_id=req.task_id,
        ))
