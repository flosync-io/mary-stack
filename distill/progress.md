# distill — progress

## Now
storage.py + promote.py bucket mode done. First real promotion applied: DMC80FD-01 version `2026-06-26.1` (2 ENRICHs on fm_coolant_concentration_low; vault ledger stamped).

## Next
1. Pull updated `knowledge/DMC80FD-01.json` from Storage and commit it to the repo (`knowledge/` dir) — storage.get_knowledge("DMC80FD-01") → write locally → commit.
2. ADD stubs deferred — need human authoring (component_ref, title, guardrail, etc.) before they can write.
3. Smoke test has 1 pre-existing FAIL (BASE_KB missing schema-required fields) — fix the fixture or skip the schema check in smoke context.

## State of files
- `render.py` — done.
- `promote.py` — done; bucket mode + mark_promoted wired; legacy --knowledge/--runtime still works.
- `storage.py` — done; single Supabase I/O layer.
- `distill/tests/smoke_promotion.py` — 8/9 pass (1 pre-existing schema fixture issue).
