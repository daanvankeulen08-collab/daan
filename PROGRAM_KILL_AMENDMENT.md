# Program-kill amendment

## Purpose
This document amends a prior program-kill decision. It records facts only; it does
not assert a scientific verdict about model capability.

## What the prior kill was based on
The M2 card study returned `CEILING` and was used as a program kill. That decision
rested on **request-discrimination**: the rate at which a non-null `tool_request`
was emitted for tool-needed vs tool-not-needed tasks (both card arms kept a
request on all tool-not-needed tasks).

## Why that endpoint is invalid as a capability endpoint
Request-discrimination measures whether the model *asks* for a tool. It is not the
same construct as integration discrimination — whether the model *incorporates a
tool result* it is given. A request-side failure cannot establish a capability
failure on the result-use side.

Integration discrimination was observed in the Block B integration study: the
stored (uncertified) results show different tool-result adoption across conditions.
Block B is **not certified** (see `REPORT_INTEGRATION.md`: a post-generation
accounting field mismatch was found; no re-scoring was done). No certified claim
is made from Block B.

Null reachability is also unresolved: in the Block A null probe, neither the `anyOf`
form (F1) nor the type-array nullable form (F2) emitted a null `tool_request` in 8
calls, but two further schema forms (N1, N2) remain to be probed. The tool schema's
null branch has not been shown reachable in practice.

## Amendment
Because the kill endpoint (request-discrimination) does not measure the capability
of interest, and because integration discrimination and null reachability are not
settled, the M2 request-based kill is **withdrawn as a capability-endpoint claim**.

The program is **OPEN pending Integration V2**, which injects the tool result
directly (no request step) and measures integration discrimination with a
pre-registered confidence-interval criterion.

Nothing here claims Block B is certified. It is not.
