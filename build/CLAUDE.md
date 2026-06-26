# build/ — Block 1 (Mary herself: Dify DSL → deployed)

Read `HANDOFF-COMPLETE.md` before touching `mary.yml` — it's the v5.1 architecture + the v5.2 backlog. Read `README.md` for the layout.

## Durable rules
- **`dify_yml/machine-mary-imd-chatflow.yml` is the SOURCE OF TRUTH.** Engine (guard/engine/envelope code) and prompts (Interpret/Render) live INSIDE it today. Author here, export back — **never hand-edit a node in the Dify UI without re-exporting to this file**, or the repo and production drift.
- **The gate:** `python3 dify_yml/tests/test_engine.py` after every yml change. It extracts the guard/engine/envelope code from the yml and runs it (so it tests the real deployed logic). 18/18 must stay green. Exits non-zero on failure.
- **Engine is deterministic; LLM only Interprets (in) and Renders (out).** Every wrong move = data / logic / prompt. Constants live once (`DECLINE_FLOOR 0.45`, `TIE_BAND 0.10`, `CLARIFY_CAP 2`, `attempts_cap 4`).
- **Knowledge is single-sourced.** Mary reads `knowledge/<machine>.json`; don't let the yml's env-var knowledge copy diverge from the repo's `knowledge.json`.
- **Git-native engine/prompts = deferred (ADR-0002), do it alongside v5.2.** Until then the yml is authored directly; the extract-and-run test already guards correctness.
- **Never deploy without sign-off.** Export the yml, run the gate, then a human imports to Dify.
- **Status vocabulary:** engine writes `resolved` (was `green`) and `unresolved` (was `amber`/`red`) — matches `contracts/runtime.schema.json` enum. Never reintroduce color strings.
- **Interpret kind `other`:** greetings, filler, unclassifiable → `other`, never `symptom`. Engine: `other` at session start → INTAKE re-prompt (reported stays empty); mid-flow → re-ask current question without advancing state. Principle: advance on positive evidence only.
- **Vault write path (N16a + N16):** after N13 Persist, a parallel branch runs `vault_fields` (code node — parses `engine.out_case` string → flat vars) → `vault_write` (HTTP POST `/rest/v1/vault`, `Prefer: resolution=merge-duplicates`). Auth = `SUPABASE_SERVICE_KEY` (same as N15). No `created_at`/`updated_at` — DB defaults. Start node defaults: `machine_id=DMC80FD-01`, `operator_id=op-test`.
- **`terminal=True` does not close the conversation.** No branch node in the flow reads it; it's data only. The Dify conversation stays open after DECLINE/ESCALATE — the next operator message re-enters the full pipeline.

## v5.2 backlog (planned, not started)
P0 `no_answer` (don't let "dunno" clear a cause) · A7 wrong-machine redirect · A6 QA-flag for parameter changes (distinct from safety STOP) · clarify plausibility-floor.

Memory: read ./progress.md and ./notes.md at task start; run update-memory at task end.
