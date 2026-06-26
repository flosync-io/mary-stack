# distill/ — Block 2 (resolved sessions + sources → knowledge.json)

Read `BUILD-PLAN.md` before building anything here. Read ADR-0001 (`../docs/adr/`) for the why.

## Durable rules (do not violate)
- **Real runtime shape only.** runtime.json fields are: `id, machine, status, reported, sanity_notes, checks[{ref,ask_snapshot,answer}], attempts, matched_fm, confirmed_cause, procedure, resolution_note, _clarify`. Resolved = `status in ("green", "resolved")` (engine now writes `resolved`; old files still have `green`). Conversation id = the filename (`id` is null today). There is NO `engine_evidence`, NO `chosen`, NO `sep` — the old stub names. `view_runtime.py` is the reference reader.
- **runtime.json is engine STATE, not a transcript.** No turns live here. Distill from it; never expect history.
- **Distillation generalizes, never appends.** A resolved case updates/adds a failure mode; it never dumps the raw case into knowledge.json. knowledge.json is a contract, not a log.
- **`render.py` is the only human-render.** slug→name + `narrate()` live there once; `promote.py` and `view_runtime.py` import it. No duplicate slug logic.
- **One writer to knowledge.json.** Never overwrite in place — `_meta` version chain (version, parent_version), commit = version, `git revert` = rollback. Approved build also publishes to Supabase Storage (Mary's runtime copy).
- **`out/` is generated → gitignored.** Approved `knowledge.json` commits up in `../knowledge/`.
- Promotion routing: green + `matched_fm` in knowledge → ENRICH (→REVISE if contradicts/escalated); `matched_fm` null → ADD; non-green → skip. ENRICH/direct = provenance + count only, never a content rewrite.

- **`promote.py` is dry-run by default** (prints to stdout, writes nothing). Pass `--apply` to write `knowledge-{machine}.json` + `decision-log.json`. Flow: read the diff → re-run with `--apply` to approve.
- **ADD goes through a human-authored draft, never auto-inserted.** A new FM can't be grounded from a runtime alone (`contracts/schema.json` requires `component_ref`, `title`, `guardrail`, …). On dry-run, `promote.py` calls `draft_add(runtime, knowledge)` and writes `out/add_<conv>.draft.json` (carries `"TODO: human must author …"` sentinels). On `--apply`, it loads the completed draft and **gates** it: any remaining `TODO: human must author` substring OR schema-invalid → `ADD blocked: <conv> draft incomplete`, skipped (ENRICH/REVISE still apply — the run never aborts). A valid completed draft is merged as a **new** FM (appended; distinct from ENRICH which edits an existing FM), with `provenance:[conv]`, `evidence_count:1`, included in the version bump, and the conv added to the `mark_promoted` set. Per-draft gate validates against `contracts/schema.json` even without `--schema`; the whole-knowledge validation still only runs with explicit `--schema`.
- **No review.html.** Replaced by stdout narrative + before→after diff. Human reads the dry-run output, then re-runs with `--apply`.
- **`storage.py` is the single Supabase I/O module.** All reads/writes to Storage (mary-memory bucket) and the vault table go through `StorageClient`. Nothing else imports `requests` or touches Supabase directly. Use `source="bucket"` (live) or `source="local"` (file fixtures, smoke tests). `mark_promoted(conv_ids, version)` stamps vault rows after `--apply`; local mode is a no-op.
- **`promote.py` bucket mode:** `--machine-id DMC80FD-01` (no `--knowledge`/`--runtime`) fetches sessions via `storage.list_promotable`, blobs via `storage.get_runtime`, knowledge via `storage.get_knowledge`. `--apply` writes back via `storage.put_knowledge` and calls `storage.mark_promoted`. Legacy `--knowledge`/`--runtime` flags still work (backward compat, smoke test path).

- **`draft_add.py` produces ADD drafts via LLM.** `draft_add(runtime, knowledge) -> dict` is a pure function (no file I/O, no Supabase). Requires `OPENAI_API_KEY` in env. Uses `gpt-5.4`, `response_format={"type":"json_object"}`, temperature 0. `operator_phrases` seeded verbatim from `reported`/`resolution_note`; `component_ref`, `title`, `guardrail` emitted as `"TODO: human must author — do not fabricate"`. `id` and `provenance` stamped by Python, not the LLM. On parse failure after one retry, `RuntimeError(raw_text)` is raised — CLI writes `.draft.RAW.txt`. `OPENAI_API_KEY` is NOT in the repo `.env` (it lives in Dify); add it locally before running.

## Build order (leaf-first)
1. `render.py` — done.
2. `promote.py` — done (dry-run/--apply, deferred ADD, smoke test).
3. ~~`review.html`~~ — replaced by stdout approach (done).
4. `storage.py` — done.
5. `draft_add.py` — done (blocked on OPENAI_API_KEY for live smoke).

Memory: read ./progress.md and ./notes.md at task start; run update-memory at task end.
