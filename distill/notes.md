# distill — notes (rationale & how-things-work)

## Decisions

**review.html dropped (2026-06-25):** The browser-based review gate was replaced with stdout dry-run + `--apply`. Rationale: the terminal diff (narrative + before→after changed fields only) is faster to read than opening a browser, and the two-step flow (read → re-run with --apply) is a simpler approval path than a download button. Decision log is still written on --apply for audit trail.

**ADD candidates deferred (2026-06-25):** The knowledge schema (`contracts/schema.json` `$defs.failure_mode`) requires 7 fields: `id, component_ref, title, guardrail, case_count, symptom_signature, causes`. A runtime session can only supply `id` (derived from symptom). Everything else needs human authoring. Deferred ADDs are listed in stdout with the missing field names so the author knows exactly what to fill in.

**storage.py added (2026-06-26):** Single I/O module for the distill block. `StorageClient(source="bucket")` uses `SUPABASE_SERVICE_KEY` (falls back to `SUPABASE_API_KEY`) from `.env`. `source="local"` is file-system only (no network) — used by smoke tests so they don't need Supabase credentials. `list_promotable` queries vault with `status=eq.resolved&promoted_at=is.null`; `mark_promoted` PATCHes vault with `promoted_at=now()` and `promoted_into_version`. Dify flow uses `SUPABASE_SERVICE_KEY` as the env var name; local `.env` uses `SUPABASE_API_KEY` — storage.py tries both.

**promote.py bucket integration (2026-06-26):** `build_change(fp, rt, ...)` refactored to `build_change(conv_id, rt, ...)` — no longer derives conv_id from filename. Bucket mode adds `--machine-id` and `--source` flags; absence of `--knowledge`/`--runtime` triggers bucket path. `--apply` in bucket mode calls `storage.put_knowledge` (upserts to Storage) and `storage.mark_promoted` for active (non-deferred) changes only. First real promotion: DMC80FD-01 `2026-06-26.1` — 2 ENRICHs on `fm_coolant_concentration_low` (conv_ids `c5abedce`, `949705bb`).

## How things work

**promote.py flow:** load knowledge → for each resolved runtime, classify (enrich/revise/add) → idempotency check (skip if conv_id already in provenance) → print per-change block (narrative + diff) → on --apply: apply non-deferred changes, bump _meta version, schema-validate (if --schema given), write knowledge-{machine}.json + decision-log + candidate.json/changes.json.

**Idempotency:** conv_id = filename (since `id` is null in real files). Already-in-provenance sessions are counted as "already promoted" and skipped silently.

**evidence_count:** always derived as `len(provenance)`, never incremented independently.
