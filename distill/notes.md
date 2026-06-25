# distill — notes (rationale & how-things-work)

## Decisions

**review.html dropped (2026-06-25):** The browser-based review gate was replaced with stdout dry-run + `--apply`. Rationale: the terminal diff (narrative + before→after changed fields only) is faster to read than opening a browser, and the two-step flow (read → re-run with --apply) is a simpler approval path than a download button. Decision log is still written on --apply for audit trail.

**ADD candidates deferred (2026-06-25):** The knowledge schema (`contracts/schema.json` `$defs.failure_mode`) requires 7 fields: `id, component_ref, title, guardrail, case_count, symptom_signature, causes`. A runtime session can only supply `id` (derived from symptom). Everything else needs human authoring. Deferred ADDs are listed in stdout with the missing field names so the author knows exactly what to fill in.

## How things work

**promote.py flow:** load knowledge → for each resolved runtime, classify (enrich/revise/add) → idempotency check (skip if conv_id already in provenance) → print per-change block (narrative + diff) → on --apply: apply non-deferred changes, bump _meta version, schema-validate (if --schema given), write knowledge-{machine}.json + decision-log + candidate.json/changes.json.

**Idempotency:** conv_id = filename (since `id` is null in real files). Already-in-provenance sessions are counted as "already promoted" and skipped silently.

**evidence_count:** always derived as `len(provenance)`, never incremented independently.
