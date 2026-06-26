# distill — progress

## Now
ADD path wired end-to-end in promote.py (dry-run drafts via draft_add → out/add_<conv>.draft.json; --apply gates TODO-sentinel + schema and merges valid drafts as new FMs). Tested local (a) dry-run draft, (b) --apply blocked on unfilled TODOs, (c) --apply merges completed draft (schema-valid, provenance/evidence stamped, conv promoted, version bumped). Publish confirmed FM-agnostic. Smoke test green (still 1 pre-existing BASE_KB fixture FAIL). distill block pipeline complete.

## Next
1. Pull updated `knowledge/DMC80FD-01.json` from Storage and commit to `knowledge/` dir.
2. Smoke test: 1 pre-existing FAIL (BASE_KB fixture missing schema-required fields) — fix fixture or skip schema check in smoke context.
3. Live ADD drill in bucket mode (real Supabase): dry-run → human authors draft → --apply merges + mark_promoted stamps the vault ledger.

## State of files
- `render.py` — done.
- `promote.py` — done; bucket mode + mark_promoted + ADD draft/merge path wired.
- `storage.py` — done; single Supabase I/O layer.
- `draft_add.py` — done and smoked; OPENAI_API_KEY now in .env.
- `distill/tests/smoke_promotion.py` — 8/9 pass (1 pre-existing schema fixture issue).
