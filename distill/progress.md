# distill — progress

## Now
draft_add.py done; blocked on OPENAI_API_KEY for live smoke (key lives in Dify, not local .env).

## Next
1. Add `OPENAI_API_KEY` to local `.env` and run: `python3 distill/draft_add.py --runtime-json /tmp/synth_4axis_creep.json --out out` to confirm operator_phrases + TODO flags.
2. Pull updated `knowledge/DMC80FD-01.json` from Storage and commit to `knowledge/` dir.
3. Smoke test: 1 pre-existing FAIL (BASE_KB fixture missing schema-required fields) — fix fixture or skip schema check in smoke context.

## State of files
- `render.py` — done.
- `promote.py` — done; bucket mode + mark_promoted wired; legacy --knowledge/--runtime still works.
- `storage.py` — done; single Supabase I/O layer.
- `draft_add.py` — done; needs OPENAI_API_KEY to run smoke.
- `distill/tests/smoke_promotion.py` — 8/9 pass (1 pre-existing schema fixture issue).
