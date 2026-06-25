# build — notes (rationale & how-things-work)

## Decisions

**Status vocab renamed (2026-06-25):** green→resolved, amber/red→unresolved. Driven by contracts/runtime.schema.json which defines the enum as open/resolved/unresolved. Color strings were never in the schema; the engine was the only writer out of compliance.

**`other` kind added to Interpret (2026-06-25):** Real session 0e62ec9a had `reported: "hi"` — the operator's greeting was classified as `symptom` and poisoned the chief complaint field. The actual symptom landed in `sanity_notes`. Fix: tighten `symptom` to require a described machine problem; greetings/filler → `other`. Engine handles `other` at session start with an INTAKE re-prompt and mid-flow with a per-stage re-ask (no state advance).

## How things work

**Engine advance principle:** the engine only advances state on positive evidence (`check_answer`, `confirmation`, `closeout_info`). Any unclassifiable input (`other`) holds position and re-asks. This is why `other` mid-flow is not converted to `confirmation` — absence of signal ≠ positive confirmation.

**`reask=True` payload flag:** when the engine re-emits a move due to `other`, it sets `reask=True` in the payload. `_brief` checks for this and prepends "Didn't catch that — could you clarify?" to the Render brief, giving the LLM the right framing without duplicating re-ask logic per move type.
