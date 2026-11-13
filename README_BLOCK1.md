# Mathematical Discovery Lab — Block 1 (Safe Research Core)

Block 1 implements one complete, safe and reproducible research loop around the
local model `lfm3:latest` via Ollama:

```
LFM3 hypothesis -> research plan -> tool request -> validation
    -> isolated SymPy expansion -> independent verification
    -> research logging -> LFM3 interpretation
```

The model is never trusted: it cannot execute code, cannot call arbitrary tools,
and every answer is schema-validated. The verifier recomputes the result itself.

## Modules

| Module | Responsibility |
|---|---|
| `mdl/config.py` | One place for model, context limit (8192), token budgets and timeouts. |
| `mdl/schemas.py` | Pydantic models plus inline JSON schemas for constrained Ollama output. |
| `mdl/ollama_client.py` | Local Ollama client; single-flight lock, `think=false`, timeouts, JSON extraction. |
| `mdl/expr_parser.py` | Closed recursive-descent parser (no `eval`). Grammar: integers, variables, `+ - * ** ( )`. |
| `mdl/symbolic.py` | The only computation: exact polynomial expansion with SymPy. |
| `mdl/worker.py` | Spawned worker process with hard wall-clock timeout. |
| `mdl/orchestrator.py` | Explicit allowlist (`symbolic_expand`), schema/grammar validation, execution. |
| `mdl/verifier.py` | Independent `sympy.expand`, algebraic zero-difference check, structured reconstruction. |
| `mdl/context_engine.py` | Typed, lossless research-context representation (encode/decode). |
| `mdl/logging_store.py` | SQLite experiment record + append-only hash-chained JSONL journal. |
| `mdl/agent.py` | Staged research loop and context construction. |
| `mdl/cli.py` | `run`, `verify-log`, `model-info`. |

## Safety model

* **No model-generated code execution.** No `eval`, `exec`, `sympify`, imports,
  shell or file/network access in the tool path.
* **Closed grammar.** The parser only builds SymPy `Integer`, `Symbol`, `Add`,
  `Mul` and `Pow` nodes with non-negative integer exponents (`<= 32`).
* **Input limits.** 200 characters, 200 tokens, 10 variables, 12-digit integer
  literals, 64 nested levels. Results are capped at 2000 terms / 20000 operations.
* **Process isolation.** The expansion runs in a spawned child process. On
  timeout the child is terminated. Windows cannot apply cgroups/memory quotas
  without extra native dependencies, so the remaining risk is a CPU/RAM spike
  inside the bounded time window. The parser and term/operation limits make this
  unlikely; it is documented rather than hidden.
* **Single-flight model inference.** A process-wide lock guarantees only one
  LFM3 generation at a time.
* **No global changes.** Everything lives in the project; no service, registry,
  driver or system setting is touched. Data files are written under `data/`
  (git-ignored).

## Research Context Engine (honest status)

The context is a typed record of concepts, symbolic relations, assumptions,
conditions, negations, exceptions, notation, units, domains, hypotheses,
uncertainties, provenance and step links. Encoding is canonical JSON; decoding
is lossless (`encode -> decode -> encode` is stable and dataclass equality
holds). Tests cover conditions/negations, symbolic relations and provenance.

It is **not** a compressor. `compare_token_usage()` reports a regex-based token
estimate (not a model tokenizer). The JSON encoding is often *larger* than a
plain-text rendering; Block 1 makes no claim of token savings or quality gain.
The value is fidelity and structure, not compression.

## Storage

SQLite (`data/mdl.sqlite3`) stores one row per experiment plus one row per step.
The JSONL journal (`data/research_events.jsonl`) is append-only: every event
carries `prev_hash` and `hash`, so silent edits are detectable with:

```
.venv\Scripts\python.exe -m mdl.cli verify-log
```

## Running

Unit tests (no model required):

```
.venv\Scripts\python.exe -m pytest
```

One real end-to-end loop (requires Ollama and `lfm3:latest`):

```
.venv\Scripts\python.exe -m pytest -m live
.venv\Scripts\python.exe -m mdl.cli run --seed "Investigate whether (x + 1)^8 has only non-negative integer coefficients."
```

Model metadata:

```
.venv\Scripts\python.exe -m mdl.cli model-info
```

## Known limitations (Block 1)

* Only one tool (`symbolic_expand`).
* The context engine preserves meaning but does not yet compress or retrieve.
* The verifier checks algebraic equivalence and structured consistency; it does
  not prove a hypothesis about coefficient signs in general. LFM3 interprets the
  observed result; the verifier only certifies the computation.
* Timeout isolation is process-level, without a hard memory cap on Windows.
* No dashboard, API, accounts, ingestion, embeddings or training (out of scope).
* The live loop depends on the local model following the JSON schema; invalid
  output is retried once and then fails safely.

## Dependencies

No new dependencies were added. Block 1 uses the existing pinned environment:
Pydantic, HTTPX, SymPy, pytest (SQLite and JSONL are standard library).
