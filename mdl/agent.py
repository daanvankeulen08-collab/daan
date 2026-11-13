"""The LFM3 research agent.

The loop is deliberately staged so every model step is validated and logged:

    hypothesis -> plan -> tool request -> validation -> tool execution
    -> independent verification -> interpretation -> context encoding

The agent never executes Python from model output and never hardcodes the
scientific conclusion: LFM3 must interpret the verified result itself.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from time import perf_counter
from typing import Protocol

from pydantic import BaseModel, ValidationError

from .config import Settings
from .context_engine import (
    Assumption,
    Concept,
    HypothesisRef,
    Provenance,
    Relation,
    ResearchContext,
    StepLink,
    Uncertainty,
    compare_token_usage,
)
from .errors import (
    ModelError,
    ModelOutputError,
    ModelTimeoutError,
    ToolValidationError,
)
from .logging_store import ResearchStore
from .ollama_client import ModelResponse
from .orchestrator import ToolExecution, ToolOrchestrator
from .schemas import (
    HYPOTHESIS_SCHEMA,
    INTERPRETATION_SCHEMA,
    PLAN_SCHEMA,
    TOOL_REQUEST_SCHEMA,
    Hypothesis,
    Interpretation,
    ResearchPlan,
    SymbolicExpandResult,
    ToolRequest,
)
from .verifier import VerificationReport, VerificationStatus, verify_symbolic_expand

SYSTEM_PROMPT = (
    "You are LFM3, a careful mathematical research assistant running locally. "
    "You formulate testable hypotheses, plan exact symbolic experiments and "
    "interpret observed computational results. You never invent or assume tool "
    "results. Answer with exactly one JSON object matching the required schema. "
    "Do not use markdown or code fences."
)


class SupportsChat(Protocol):
    def chat_json(
        self, messages: list[dict], schema: dict | None, *, num_predict: int
    ) -> ModelResponse: ...

    def model_info(self) -> dict | None: ...


@dataclass
class ExperimentOutcome:
    experiment_id: str
    status: str
    hypothesis: Hypothesis
    plan: ResearchPlan
    tool_request: ToolRequest
    tool_result: SymbolicExpandResult | None = None
    tool_latency_ms: float | None = None
    verification: VerificationReport | None = None
    interpretation: Interpretation | None = None
    rejection: str | None = None
    latency_ms: float = 0.0
    token_usage: dict | None = None
    context: ResearchContext | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class ResearchAgent:
    def __init__(
        self,
        settings: Settings,
        client: SupportsChat,
        orchestrator: ToolOrchestrator,
        store: ResearchStore,
    ) -> None:
        self.settings = settings
        self.client = client
        self.orchestrator = orchestrator
        self.store = store

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------
    def run(
        self, seed: str | None = None, *, allow_repair: bool = True
    ) -> ExperimentOutcome:
        started = perf_counter()
        token_usage: dict[str, int] = {
            "prompt_eval_count": 0,
            "eval_count": 0,
            "model_calls": 0,
        }

        digest: str | None = None
        try:
            info = self.client.model_info()
            if info:
                digest = info.get("digest")
        except ModelError:
            digest = None

        experiment_id = self.store.create_experiment(
            seed=seed,
            model=self.settings.model,
            model_digest=digest,
            parameters=self._parameters(),
            context_limit=self.settings.context_limit,
        )

        hypothesis: Hypothesis | None = None
        plan: ResearchPlan | None = None
        request: ToolRequest | None = None
        execution: ToolExecution | None = None
        verification: VerificationReport | None = None
        interpretation: Interpretation | None = None
        context: ResearchContext | None = None
        rejection: str | None = None

        try:
            hypothesis = self.formulate_hypothesis(
                experiment_id, seed, token_usage
            )
            self.store.set_experiment_fields(
                experiment_id, hypothesis_json=hypothesis.model_dump()
            )

            plan = self.make_plan(experiment_id, hypothesis, token_usage)
            self.store.set_experiment_fields(
                experiment_id, plan_json=plan.model_dump()
            )

            request = self.request_tool(
                experiment_id, hypothesis, plan, token_usage
            )
            self.store.set_experiment_fields(
                experiment_id, tool_request_json=request.model_dump()
            )

            # ---- validation gate -------------------------------------
            try:
                self.orchestrator.validate(request)
                self.store.log_step(
                    experiment_id,
                    "tool_validation",
                    "accepted",
                    {
                        "tool": request.tool,
                        "expression": request.arguments.expression,
                    },
                )
            except ToolValidationError as exc:
                rejection = str(exc)
                self.store.log_step(
                    experiment_id,
                    "tool_validation",
                    "rejected",
                    {
                        "request": request.model_dump(),
                        "error": rejection,
                    },
                )
                if not allow_repair:
                    return self._finish_rejected(
                        experiment_id,
                        started,
                        token_usage,
                        hypothesis,
                        plan,
                        request,
                        rejection,
                    )

                request = self.repair_tool_request(
                    experiment_id,
                    hypothesis,
                    plan,
                    rejection,
                    token_usage,
                )
                self.store.set_experiment_fields(
                    experiment_id, tool_request_json=request.model_dump()
                )
                try:
                    self.orchestrator.validate(request)
                    self.store.log_step(
                        experiment_id,
                        "tool_validation",
                        "accepted_after_repair",
                        {
                            "tool": request.tool,
                            "expression": request.arguments.expression,
                        },
                    )
                except ToolValidationError as exc2:
                    rejection = str(exc2)
                    self.store.log_step(
                        experiment_id,
                        "tool_validation",
                        "rejected_after_repair",
                        {"request": request.model_dump(), "error": rejection},
                    )
                    return self._finish_rejected(
                        experiment_id,
                        started,
                        token_usage,
                        hypothesis,
                        plan,
                        request,
                        rejection,
                    )

            # ---- execution -------------------------------------------
            execution = self.orchestrator.execute(request)
            self.store.log_step(
                experiment_id,
                "tool_execution",
                "ok",
                {"result": execution.result.model_dump()},
                latency_ms=execution.latency_ms,
            )
            self.store.set_experiment_fields(
                experiment_id, tool_result_json=execution.result.model_dump()
            )

            # ---- independent verification ----------------------------
            verification = verify_symbolic_expand(
                request.arguments.expression, execution.result
            )
            self.store.log_step(
                experiment_id,
                "verification",
                verification.status.value,
                verification.to_dict(),
            )
            self.store.set_experiment_fields(
                experiment_id, verification_json=verification.to_dict()
            )

            # ---- interpretation --------------------------------------
            interpretation = self.interpret(
                experiment_id,
                hypothesis,
                plan,
                request,
                execution.result,
                verification,
                token_usage,
            )
            self.store.set_experiment_fields(
                experiment_id, interpretation_json=interpretation.model_dump()
            )

            # ---- context encoding ------------------------------------
            context = build_context(
                experiment_id,
                hypothesis,
                plan,
                request,
                execution.result,
                verification,
                interpretation,
            )
            token_comparison = compare_token_usage(context)
            self.store.set_experiment_fields(
                experiment_id, context_json=context.encode()
            )
            self.store.log_step(
                experiment_id,
                "context_encode",
                "ok",
                {
                    "context": context.to_dict(),
                    "token_comparison": token_comparison,
                },
            )

            latency_ms = (perf_counter() - started) * 1000.0
            self.store.finish_experiment(
                experiment_id,
                "completed",
                latency_ms=latency_ms,
                token_usage=token_usage,
            )
            return ExperimentOutcome(
                experiment_id=experiment_id,
                status="completed",
                hypothesis=hypothesis,
                plan=plan,
                tool_request=request,
                tool_result=execution.result,
                tool_latency_ms=execution.latency_ms,
                verification=verification,
                interpretation=interpretation,
                latency_ms=latency_ms,
                token_usage=token_usage,
                context=context,
            )

        except Exception as exc:
            latency_ms = (perf_counter() - started) * 1000.0
            try:
                self.store.log_step(
                    experiment_id,
                    "error",
                    "failed",
                    {"type": type(exc).__name__, "error": str(exc)},
                )
                self.store.finish_experiment(
                    experiment_id,
                    "failed",
                    error=str(exc),
                    latency_ms=latency_ms,
                    token_usage=token_usage,
                )
            finally:
                raise

    # ------------------------------------------------------------------
    # Model steps
    # ------------------------------------------------------------------
    def formulate_hypothesis(
        self,
        experiment_id: str,
        seed: str | None,
        token_usage: dict[str, int],
    ) -> Hypothesis:
        instruction = seed or (
            "Choose a simple polynomial identity or coefficient property that can "
            "be investigated with exact symbolic expansion."
        )
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Research seed: {instruction}\n\n"
                    "Formulate ONE precise, testable mathematical hypothesis about "
                    "the expansion of a polynomial expression. It must be checkable "
                    "with exact symbolic expansion. State the variables involved and "
                    "list every assumption that is required. Keep the expression "
                    "small (low degree, at most two variables)."
                ),
            },
        ]
        return self._model_step(
            experiment_id,
            "hypothesis",
            messages,
            HYPOTHESIS_SCHEMA,
            Hypothesis,
            self.settings.hypothesis_max_tokens,
            token_usage,
        )

    def make_plan(
        self,
        experiment_id: str,
        hypothesis: Hypothesis,
        token_usage: dict[str, int],
    ) -> ResearchPlan:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "Hypothesis JSON:\n"
                    + json.dumps(hypothesis.model_dump(), ensure_ascii=False)
                    + "\n\nProduce a short research plan (2 to 5 steps). The only "
                    "available tool is symbolic_expand, which expands a polynomial "
                    "expression exactly with SymPy. State the expected outcome."
                ),
            },
        ]
        return self._model_step(
            experiment_id,
            "plan",
            messages,
            PLAN_SCHEMA,
            ResearchPlan,
            self.settings.plan_max_tokens,
            token_usage,
        )

    def request_tool(
        self,
        experiment_id: str,
        hypothesis: Hypothesis,
        plan: ResearchPlan,
        token_usage: dict[str, int],
    ) -> ToolRequest:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "Hypothesis JSON:\n"
                    + json.dumps(hypothesis.model_dump(), ensure_ascii=False)
                    + "\n\nPlan JSON:\n"
                    + json.dumps(plan.model_dump(), ensure_ascii=False)
                    + "\n\nRequest exactly one symbolic_expand call for the "
                    "polynomial expression at the heart of the hypothesis. The "
                    "expression grammar allows only integers, variable names, "
                    "parentheses and the operators + - * **. No division, no "
                    "functions, no decimals. Maximum exponent is 32."
                ),
            },
        ]
        return self._model_step(
            experiment_id,
            "tool_request",
            messages,
            TOOL_REQUEST_SCHEMA,
            ToolRequest,
            self.settings.tool_request_max_tokens,
            token_usage,
        )

    def repair_tool_request(
        self,
        experiment_id: str,
        hypothesis: Hypothesis,
        plan: ResearchPlan,
        rejection: str,
        token_usage: dict[str, int],
    ) -> ToolRequest:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "Your previous tool request was rejected by the validator.\n"
                    f"Reason: {rejection}\n\n"
                    "Hypothesis JSON:\n"
                    + json.dumps(hypothesis.model_dump(), ensure_ascii=False)
                    + "\n\nPlan JSON:\n"
                    + json.dumps(plan.model_dump(), ensure_ascii=False)
                    + "\n\nReturn one corrected symbolic_expand request. Use only "
                    "integers, variable names, parentheses and + - * **."
                ),
            },
        ]
        return self._model_step(
            experiment_id,
            "tool_request_repair",
            messages,
            TOOL_REQUEST_SCHEMA,
            ToolRequest,
            self.settings.tool_request_max_tokens,
            token_usage,
        )

    def interpret(
        self,
        experiment_id: str,
        hypothesis: Hypothesis,
        plan: ResearchPlan,
        request: ToolRequest,
        result: SymbolicExpandResult,
        verification: VerificationReport,
        token_usage: dict[str, int],
    ) -> Interpretation:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "Hypothesis JSON:\n"
                    + json.dumps(hypothesis.model_dump(), ensure_ascii=False)
                    + "\n\nTool request JSON:\n"
                    + json.dumps(request.model_dump(), ensure_ascii=False)
                    + "\n\nTool result JSON:\n"
                    + json.dumps(result.model_dump(), ensure_ascii=False)
                    + "\n\nIndependent verification JSON:\n"
                    + json.dumps(verification.to_dict(), ensure_ascii=False)
                    + "\n\nInterpret the observed result yourself. State whether it "
                    "supports the hypothesis, describe the observed outcome in your "
                    "own words, list remaining uncertainties and propose concrete "
                    "follow-up work. Do not merely repeat the expanded expression. "
                    "Be concise: at most three sentences in the conclusion, and at "
                    "most three short items in each list."
                ),
            },
        ]
        return self._model_step(
            experiment_id,
            "interpretation",
            messages,
            INTERPRETATION_SCHEMA,
            Interpretation,
            self.settings.interpretation_max_tokens,
            token_usage,
        )

    # ------------------------------------------------------------------
    # Shared model-call handling
    # ------------------------------------------------------------------
    def _model_step(
        self,
        experiment_id: str,
        phase: str,
        messages: list[dict],
        schema: dict,
        model_class: type[BaseModel],
        num_predict: int,
        token_usage: dict[str, int],
    ) -> BaseModel:
        current = list(messages)
        last_error: Exception | None = None

        for attempt in (1, 2):
            started = perf_counter()
            try:
                response = self.client.chat_json(
                    current, schema, num_predict=num_predict
                )
            except ModelTimeoutError as exc:
                self.store.log_step(
                    experiment_id,
                    "model_call",
                    "timeout",
                    {"phase": phase, "attempt": attempt, "error": str(exc)},
                    latency_ms=(perf_counter() - started) * 1000.0,
                )
                raise
            except ModelOutputError as exc:
                self.store.log_step(
                    experiment_id,
                    "model_call",
                    "invalid_json",
                    {"phase": phase, "attempt": attempt, "error": str(exc)},
                    latency_ms=(perf_counter() - started) * 1000.0,
                )
                if attempt == 1:
                    current = current + [
                        {
                            "role": "user",
                            "content": (
                                "Your previous response was not valid JSON. "
                                "Return exactly one short JSON object matching "
                                "the schema, with no extra prose."
                            ),
                        }
                    ]
                    continue
                raise
            except ModelError as exc:
                self.store.log_step(
                    experiment_id,
                    "model_call",
                    "failed",
                    {"phase": phase, "attempt": attempt, "error": str(exc)},
                    latency_ms=(perf_counter() - started) * 1000.0,
                )
                raise

            latency_ms = (perf_counter() - started) * 1000.0
            token_usage["model_calls"] += 1
            token_usage["prompt_eval_count"] += int(
                response.prompt_eval_count or 0
            )
            token_usage["eval_count"] += int(response.eval_count or 0)

            if response.done_reason == "length":
                last_error = ModelOutputError(
                    f"{phase}: model output was truncated at the token limit"
                )
                self.store.log_step(
                    experiment_id,
                    "model_call",
                    "truncated",
                    {
                        "phase": phase,
                        "attempt": attempt,
                        "done_reason": response.done_reason,
                        "eval_count": response.eval_count,
                        "content": response.content[:4000],
                    },
                    latency_ms=latency_ms,
                )
                if attempt == 1:
                    current = current + [
                        {"role": "assistant", "content": response.content},
                        {
                            "role": "user",
                            "content": (
                                "Your previous answer was cut off. Return the same "
                                "JSON but much shorter: at most two sentences per "
                                "text field and at most three list items."
                            ),
                        },
                    ]
                    continue
                raise last_error

            try:
                parsed = model_class.model_validate(response.parsed)
            except ValidationError as exc:
                last_error = exc
                self.store.log_step(
                    experiment_id,
                    "model_call",
                    "invalid_schema",
                    {
                        "phase": phase,
                        "attempt": attempt,
                        "error": str(exc),
                        "content": response.content[:4000],
                    },
                    latency_ms=latency_ms,
                )
                current = current + [
                    {"role": "assistant", "content": response.content},
                    {
                        "role": "user",
                        "content": (
                            "Your previous answer did not match the required "
                            f"schema: {exc}. Return only one valid JSON object."
                        ),
                    },
                ]
                continue

            self.store.log_step(
                experiment_id,
                "model_call",
                "ok",
                {
                    "phase": phase,
                    "attempt": attempt,
                    "content": response.content[:4000],
                    "prompt_eval_count": response.prompt_eval_count,
                    "eval_count": response.eval_count,
                    "wall_ms": round(response.wall_ms, 2),
                },
                latency_ms=latency_ms,
            )
            return parsed

        raise ModelOutputError(
            f"{phase}: model output remained invalid after 2 attempts: {last_error}"
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _parameters(self) -> dict:
        return {
            "temperature": self.settings.temperature,
            "top_p": self.settings.top_p,
            "repeat_penalty": self.settings.repeat_penalty,
            "seed": self.settings.seed,
            "think": self.settings.think,
            "context_limit": self.settings.context_limit,
            "keep_alive": self.settings.keep_alive,
            "max_tokens": {
                "hypothesis": self.settings.hypothesis_max_tokens,
                "plan": self.settings.plan_max_tokens,
                "tool_request": self.settings.tool_request_max_tokens,
                "interpretation": self.settings.interpretation_max_tokens,
            },
        }

    def _finish_rejected(
        self,
        experiment_id: str,
        started: float,
        token_usage: dict[str, int],
        hypothesis: Hypothesis,
        plan: ResearchPlan,
        request: ToolRequest,
        rejection: str,
    ) -> ExperimentOutcome:
        latency_ms = (perf_counter() - started) * 1000.0
        self.store.finish_experiment(
            experiment_id,
            "rejected",
            error=rejection,
            latency_ms=latency_ms,
            token_usage=token_usage,
        )
        return ExperimentOutcome(
            experiment_id=experiment_id,
            status="rejected",
            hypothesis=hypothesis,
            plan=plan,
            tool_request=request,
            rejection=rejection,
            latency_ms=latency_ms,
            token_usage=token_usage,
        )


# ---------------------------------------------------------------------------
# Context construction
# ---------------------------------------------------------------------------


def build_context(
    experiment_id: str,
    hypothesis: Hypothesis,
    plan: ResearchPlan,
    request: ToolRequest,
    result: SymbolicExpandResult,
    verification: VerificationReport,
    interpretation: Interpretation,
) -> ResearchContext:
    now = _utc_now()

    if verification.status is VerificationStatus.PASSED:
        status = "supported" if interpretation.supports_hypothesis else "refuted"
    else:
        status = "unknown"

    concepts = tuple(
        Concept(
            name=variable,
            definition="variable appearing in the hypothesis",
            notation=variable,
        )
        for variable in hypothesis.variables
    )

    relations = (
        Relation(
            lhs=result.expression,
            operator="=",
            rhs=result.expanded,
            conditions=(),
            exceptions=(),
        ),
    )

    assumptions = tuple(
        Assumption(statement=statement, kind="assumption")
        for statement in hypothesis.assumptions
    )

    hypotheses = (
        HypothesisRef(
            statement=hypothesis.statement,
            status=status,
            experiment_id=experiment_id,
        ),
    )

    uncertainties = tuple(
        Uncertainty(statement=statement, reason="reported by LFM3")
        for statement in interpretation.uncertainties
    )

    provenance = tuple(
        Provenance(
            experiment_id=experiment_id,
            step=step,
            source=source,
            reference=None,
            timestamp=now,
        )
        for step, source in (
            ("hypothesis", "lfm3"),
            ("plan", "lfm3"),
            ("tool_request", "lfm3"),
            ("tool_execution", "sympy"),
            ("verification", "verifier"),
            ("interpretation", "lfm3"),
        )
    )

    verification_relation = (
        "supports"
        if verification.status is VerificationStatus.PASSED
        else "depends_on"
    )
    step_links = (
        StepLink("hypothesis", "plan", "refines"),
        StepLink("plan", "tool_request", "depends_on"),
        StepLink("tool_request", "tool_execution", "depends_on"),
        StepLink("tool_execution", "verification", "depends_on"),
        StepLink("verification", "interpretation", verification_relation),
    )

    return ResearchContext(
        concepts=concepts,
        relations=relations,
        assumptions=assumptions,
        notation=tuple(hypothesis.variables),
        hypotheses=hypotheses,
        uncertainties=uncertainties,
        provenance=provenance,
        step_links=step_links,
    )
