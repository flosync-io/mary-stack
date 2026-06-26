# build — notes (rationale & how-things-work)

## Decisions

**Status vocab renamed (2026-06-25):** green→resolved, amber/red→unresolved. Driven by contracts/runtime.schema.json which defines the enum as open/resolved/unresolved. Color strings were never in the schema; the engine was the only writer out of compliance.

**`other` kind added to Interpret (2026-06-25):** Real session 0e62ec9a had `reported: "hi"` — the operator's greeting was classified as `symptom` and poisoned the chief complaint field. The actual symptom landed in `sanity_notes`. Fix: tighten `symptom` to require a described machine problem; greetings/filler → `other`. Engine handles `other` at session start with an INTAKE re-prompt and mid-flow with a per-stage re-ask (no state advance).

**Vault write path added (2026-06-26):** The flow previously wrote only to Storage (`/storage/v1/object/mary-memory/runtime/...`). There was no vault row writer. Added N16a `vault_fields` (code node, parses `engine.out_case` JSON string and outputs `v_status`/`v_fault_type`/`v_resolution` as flat strings) → N16 `vault_write` (HTTP POST to `/rest/v1/vault`). Dify's template engine cannot dot-path into a JSON blob variable (e.g. `{{#engine.out_case.status#}}` doesn't resolve) — hence the intermediate code node. Upsert strategy: `Prefer: resolution=merge-duplicates` on the `conversation_id` PK, so each turn updates the row in place and the DB-default `created_at` is preserved. Uses `SUPABASE_SERVICE_KEY` (service-role, bypasses RLS) — same credential as N15. `v_resolution` fallback chain: `resolution_note` (CLOSEOUT path) → reconstructed `"resolved via {procedure}; cause {confirmed_cause}"` (Mary-led RESOLVED, confirmed by inspecting real session c5abedce) → `""`. `resolution_note` is absent on Mary-led closes; only `procedure` + `confirmed_cause` are written to runtime.json in that path.

## How things work

**Engine advance principle:** the engine only advances state on positive evidence (`check_answer`, `confirmation`, `closeout_info`). Any unclassifiable input (`other`) holds position and re-asks. This is why `other` mid-flow is not converted to `confirmation` — absence of signal ≠ positive confirmation.

**`reask=True` payload flag:** when the engine re-emits a move due to `other`, it sets `reask=True` in the payload. `_brief` checks for this and prepends "Didn't catch that — could you clarify?" to the Render brief, giving the LLM the right framing without duplicating re-ask logic per move type.
