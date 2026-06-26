# distill — progress

## Now
draft_add.py fully smoked: operator_phrases verbatim, TODO sentinels correct, alarm_codes=[], cause derived from resolution_note. distill block core pipeline complete.

## Next
1. Pull updated `knowledge/DMC80FD-01.json` from Storage and commit to `knowledge/` dir.
2. Smoke test: 1 pre-existing FAIL (BASE_KB fixture missing schema-required fields) — fix fixture or skip schema check in smoke context.
3. Wire draft_add into promote.py — on deferred ADD, emit a draft automatically alongside the decision log.

## State of files
- `render.py` — done.
- `promote.py` — done; bucket mode + mark_promoted wired.
- `storage.py` — done; single Supabase I/O layer.
- `draft_add.py` — done and smoked; OPENAI_API_KEY now in .env.
- `distill/tests/smoke_promotion.py` — 8/9 pass (1 pre-existing schema fixture issue).
