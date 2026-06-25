# distill/ — Block 2 (resolved sessions + sources → knowledge.json)

Read `BUILD-PLAN.md` before building anything here. Read ADR-0001 (`../docs/adr/`) for the why.

## Durable rules (do not violate)
- **Real runtime shape only.** runtime.json fields are: `id, machine, status, reported, sanity_notes, checks[{ref,ask_snapshot,answer}], attempts, matched_fm, confirmed_cause, procedure, resolution_note, _clarify`. Resolved = `status == "green"`. Conversation id = the filename (`id` is null today). There is NO `engine_evidence`, NO `chosen`, NO `sep` — the old stub names. `view_runtime.py` is the reference reader.
- **runtime.json is engine STATE, not a transcript.** No turns live here. Distill from it; never expect history.
- **Distillation generalizes, never appends.** A resolved case updates/adds a failure mode; it never dumps the raw case into knowledge.json. knowledge.json is a contract, not a log.
- **`render.py` is the only human-render.** slug→name + `narrate()` live there once; `promote.py` and `view_runtime.py` import it. No duplicate slug logic.
- **One writer to knowledge.json.** Never overwrite in place — `_meta` version chain (version, parent_version), commit = version, `git revert` = rollback. Approved build also publishes to Supabase Storage (Mary's runtime copy).
- **`out/` is generated → gitignored.** Approved `knowledge.json` commits up in `../knowledge/`.
- Promotion routing: green + `matched_fm` in knowledge → ENRICH (→REVISE if contradicts/escalated); `matched_fm` null → ADD; non-green → skip. ENRICH/direct = provenance + count only, never a content rewrite.

## Build order (leaf-first)
1. `render.py` — `narrate(runtime, knowledge)`, `name_of(slug, knowledge)`. Done when it reproduces the 3 sample narratives.
2. `promote.py` — adapt the reader to the real shape; route enrich/add/revise; ground with `render.narrate()`. Done when `sample/real-runtime` → 1 ENRICH (coolant), 2 skipped (open).
3. `review.html` — narrative grounding per change; approve → versioned download + decision log.

Memory: read ./progress.md and ./notes.md at task start; run update-memory at task end.
