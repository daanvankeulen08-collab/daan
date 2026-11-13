"""Minimal Research Context Engine.

Design goal: preserve meaning, not compress text.  The encoding is canonical
JSON built from explicit typed fields.  Every field survives a round trip
exactly; no summarisation or lossy rewriting is performed.

Token figures produced here are *estimates* from a regex tokenizer, not a
model tokenizer.  Block 1 makes no claim that JSON is cheaper than prose.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from .errors import ContextError

CONTEXT_VERSION = 1
ASSUMPTION_KINDS = frozenset({"assumption", "condition", "negation", "exception"})
HYPOTHESIS_STATUSES = frozenset({"proposed", "supported", "refuted", "unknown"})
STEP_RELATIONS = frozenset({"depends_on", "supports", "contradicts", "refines"})


@dataclass(frozen=True)
class Concept:
    name: str
    definition: str = ""
    notation: str | None = None
    domain: str | None = None
    units: str | None = None


@dataclass(frozen=True)
class Relation:
    lhs: str
    operator: str
    rhs: str
    conditions: tuple[str, ...] = ()
    exceptions: tuple[str, ...] = ()


@dataclass(frozen=True)
class Assumption:
    statement: str
    kind: str = "assumption"
    scope: str | None = None


@dataclass(frozen=True)
class HypothesisRef:
    statement: str
    status: str = "unknown"
    experiment_id: str | None = None


@dataclass(frozen=True)
class Uncertainty:
    statement: str
    reason: str = ""
    resolved: bool = False


@dataclass(frozen=True)
class Provenance:
    experiment_id: str
    step: str
    source: str
    reference: str | None = None
    timestamp: str | None = None


@dataclass(frozen=True)
class StepLink:
    from_step: str
    to_step: str
    relation: str
    note: str = ""


@dataclass(frozen=True)
class ResearchContext:
    version: int = CONTEXT_VERSION
    concepts: tuple[Concept, ...] = ()
    relations: tuple[Relation, ...] = ()
    assumptions: tuple[Assumption, ...] = ()
    notation: tuple[str, ...] = ()
    units: tuple[str, ...] = ()
    domains: tuple[str, ...] = ()
    hypotheses: tuple[HypothesisRef, ...] = ()
    uncertainties: tuple[Uncertainty, ...] = ()
    provenance: tuple[Provenance, ...] = ()
    step_links: tuple[StepLink, ...] = ()

    # -- encoding --------------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "concepts": [
                {
                    "name": c.name,
                    "definition": c.definition,
                    "notation": c.notation,
                    "domain": c.domain,
                    "units": c.units,
                }
                for c in self.concepts
            ],
            "relations": [
                {
                    "lhs": r.lhs,
                    "operator": r.operator,
                    "rhs": r.rhs,
                    "conditions": list(r.conditions),
                    "exceptions": list(r.exceptions),
                }
                for r in self.relations
            ],
            "assumptions": [
                {"statement": a.statement, "kind": a.kind, "scope": a.scope}
                for a in self.assumptions
            ],
            "notation": list(self.notation),
            "units": list(self.units),
            "domains": list(self.domains),
            "hypotheses": [
                {
                    "statement": h.statement,
                    "status": h.status,
                    "experiment_id": h.experiment_id,
                }
                for h in self.hypotheses
            ],
            "uncertainties": [
                {
                    "statement": u.statement,
                    "reason": u.reason,
                    "resolved": u.resolved,
                }
                for u in self.uncertainties
            ],
            "provenance": [
                {
                    "experiment_id": p.experiment_id,
                    "step": p.step,
                    "source": p.source,
                    "reference": p.reference,
                    "timestamp": p.timestamp,
                }
                for p in self.provenance
            ],
            "step_links": [
                {
                    "from_step": s.from_step,
                    "to_step": s.to_step,
                    "relation": s.relation,
                    "note": s.note,
                }
                for s in self.step_links
            ],
        }

    def encode(self) -> str:
        return json.dumps(
            self.to_dict(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    @classmethod
    def decode(cls, text: str) -> "ResearchContext":
        try:
            data = json.loads(text)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ContextError(f"invalid context JSON: {exc}") from exc
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict) -> "ResearchContext":
        try:
            if not isinstance(data, dict):
                raise ContextError("context must be a JSON object")
            version = int(data.get("version", 0))
            if version != CONTEXT_VERSION:
                raise ContextError(f"unsupported context version {version}")

            context = cls(
                version=version,
                concepts=tuple(_concept(item) for item in _list(data, "concepts")),
                relations=tuple(_relation(item) for item in _list(data, "relations")),
                assumptions=tuple(
                    _assumption(item) for item in _list(data, "assumptions")
                ),
                notation=_str_tuple(data, "notation"),
                units=_str_tuple(data, "units"),
                domains=_str_tuple(data, "domains"),
                hypotheses=tuple(
                    _hypothesis(item) for item in _list(data, "hypotheses")
                ),
                uncertainties=tuple(
                    _uncertainty(item) for item in _list(data, "uncertainties")
                ),
                provenance=tuple(
                    _provenance(item) for item in _list(data, "provenance")
                ),
                step_links=tuple(
                    _step_link(item) for item in _list(data, "step_links")
                ),
            )
        except ContextError:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise ContextError(f"invalid context structure: {exc}") from exc

        _validate(context)
        return context

    # -- rendering -------------------------------------------------------
    def to_plain_text(self) -> str:
        """Lossless prose rendering, used only for token comparisons."""

        def q(value: object) -> str:
            return json.dumps(value, ensure_ascii=False)

        lines = [f"VERSION {self.version}"]
        for c in self.concepts:
            lines.append(
                "CONCEPT "
                f"name={q(c.name)} definition={q(c.definition)} "
                f"notation={q(c.notation)} domain={q(c.domain)} "
                f"units={q(c.units)}"
            )
        for r in self.relations:
            lines.append(
                "RELATION "
                f"lhs={q(r.lhs)} operator={q(r.operator)} rhs={q(r.rhs)} "
                f"conditions={q(list(r.conditions))} "
                f"exceptions={q(list(r.exceptions))}"
            )
        for a in self.assumptions:
            lines.append(
                "ASSUMPTION "
                f"statement={q(a.statement)} kind={q(a.kind)} scope={q(a.scope)}"
            )
        for v in self.notation:
            lines.append(f"NOTATION {q(v)}")
        for v in self.units:
            lines.append(f"UNIT {q(v)}")
        for v in self.domains:
            lines.append(f"DOMAIN {q(v)}")
        for h in self.hypotheses:
            lines.append(
                "HYPOTHESIS "
                f"statement={q(h.statement)} status={q(h.status)} "
                f"experiment_id={q(h.experiment_id)}"
            )
        for u in self.uncertainties:
            lines.append(
                "UNCERTAINTY "
                f"statement={q(u.statement)} reason={q(u.reason)} "
                f"resolved={q(u.resolved)}"
            )
        for p in self.provenance:
            lines.append(
                "PROVENANCE "
                f"experiment_id={q(p.experiment_id)} step={q(p.step)} "
                f"source={q(p.source)} reference={q(p.reference)} "
                f"timestamp={q(p.timestamp)}"
            )
        for s in self.step_links:
            lines.append(
                "STEP_LINK "
                f"from_step={q(s.from_step)} to_step={q(s.to_step)} "
                f"relation={q(s.relation)} note={q(s.note)}"
            )
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _list(data: dict, key: str) -> list:
    value = data.get(key, [])
    if not isinstance(value, list):
        raise ContextError(f"{key} must be a list")
    return value


def _str(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ContextError(f"{field_name} must be a string")
    return value


def _opt_str(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    return _str(value, field_name)


def _str_tuple(data: dict, key: str) -> tuple[str, ...]:
    values = _list(data, key)
    return tuple(_str(value, key) for value in values)


def _obj(item: object, kind: str) -> dict:
    if not isinstance(item, dict):
        raise ContextError(f"{kind} entries must be objects")
    return item


def _concept(item: object) -> Concept:
    data = _obj(item, "concept")
    return Concept(
        name=_str(data["name"], "concept.name"),
        definition=_str(data.get("definition", ""), "concept.definition"),
        notation=_opt_str(data.get("notation"), "concept.notation"),
        domain=_opt_str(data.get("domain"), "concept.domain"),
        units=_opt_str(data.get("units"), "concept.units"),
    )


def _relation(item: object) -> Relation:
    data = _obj(item, "relation")
    return Relation(
        lhs=_str(data["lhs"], "relation.lhs"),
        operator=_str(data["operator"], "relation.operator"),
        rhs=_str(data["rhs"], "relation.rhs"),
        conditions=_str_tuple(data, "conditions"),
        exceptions=_str_tuple(data, "exceptions"),
    )


def _assumption(item: object) -> Assumption:
    data = _obj(item, "assumption")
    return Assumption(
        statement=_str(data["statement"], "assumption.statement"),
        kind=_str(data.get("kind", "assumption"), "assumption.kind"),
        scope=_opt_str(data.get("scope"), "assumption.scope"),
    )


def _hypothesis(item: object) -> HypothesisRef:
    data = _obj(item, "hypothesis")
    return HypothesisRef(
        statement=_str(data["statement"], "hypothesis.statement"),
        status=_str(data.get("status", "unknown"), "hypothesis.status"),
        experiment_id=_opt_str(
            data.get("experiment_id"), "hypothesis.experiment_id"
        ),
    )


def _uncertainty(item: object) -> Uncertainty:
    data = _obj(item, "uncertainty")
    resolved = data.get("resolved", False)
    if not isinstance(resolved, bool):
        raise ContextError("uncertainty.resolved must be a boolean")
    return Uncertainty(
        statement=_str(data["statement"], "uncertainty.statement"),
        reason=_str(data.get("reason", ""), "uncertainty.reason"),
        resolved=resolved,
    )


def _provenance(item: object) -> Provenance:
    data = _obj(item, "provenance")
    return Provenance(
        experiment_id=_str(data["experiment_id"], "provenance.experiment_id"),
        step=_str(data["step"], "provenance.step"),
        source=_str(data["source"], "provenance.source"),
        reference=_opt_str(data.get("reference"), "provenance.reference"),
        timestamp=_opt_str(data.get("timestamp"), "provenance.timestamp"),
    )


def _step_link(item: object) -> StepLink:
    data = _obj(item, "step_link")
    return StepLink(
        from_step=_str(data["from_step"], "step_link.from_step"),
        to_step=_str(data["to_step"], "step_link.to_step"),
        relation=_str(data["relation"], "step_link.relation"),
        note=_str(data.get("note", ""), "step_link.note"),
    )


def _validate(context: ResearchContext) -> None:
    for assumption in context.assumptions:
        if assumption.kind not in ASSUMPTION_KINDS:
            raise ContextError(f"invalid assumption kind {assumption.kind!r}")
    for hypothesis in context.hypotheses:
        if hypothesis.status not in HYPOTHESIS_STATUSES:
            raise ContextError(f"invalid hypothesis status {hypothesis.status!r}")
    for link in context.step_links:
        if link.relation not in STEP_RELATIONS:
            raise ContextError(f"invalid step relation {link.relation!r}")


# ---------------------------------------------------------------------------
# Token estimates (explicitly approximate)
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"\w+|[^\w\s]")


def estimate_tokens(text: str) -> int:
    """Cheap, deterministic token estimate; not a model tokenizer."""

    return len(_TOKEN_RE.findall(text))


def compare_token_usage(context: ResearchContext) -> dict:
    encoded = context.encode()
    plain = context.to_plain_text()
    json_tokens = estimate_tokens(encoded)
    plain_tokens = estimate_tokens(plain)
    ratio = round(json_tokens / plain_tokens, 4) if plain_tokens else None
    return {
        "json_tokens": json_tokens,
        "plain_tokens": plain_tokens,
        "json_to_plain_ratio": ratio,
        "method": "regex word/punctuation estimate, not a model tokenizer",
    }
