# distill — progress

## Now
Promotion loop CLOSED end to end (ENRICH + ADD) on live infra. First production ADD merged: conv 9cc87d7e (closeout-on-decline) → draft → human-authored → apply/publish → **v2026-06-26.2**, vault stamped, committed (5bfc7ea). Gate-5 reachability proven (0.18 decline → 0.99 match, same symptom). ENRICH already proven (coolant FM, 2026-06-26.1).

## Next (findings to chase)
1. **DECLINE unreachable via clarify-rejection** — the other-re-ask + clarify-cap deadlock; closeout rescued this session. Engine-side.
2. **bunched-but-all-low → clarify instead of decline** — plausibility-floor case, live repro.
3. **ADD merge inserts only the FM** — real ADDs drag new components/checks/procedures/steps; merge should handle the whole dependency set (today a one-shot script does it).
4. **Author the 4 dangling `stp_` refs** on `proc_replace_clamp_cylinder_seal` (`stp_loto_dump_accumulator`, `stp_open_clamp_cylinder`, `stp_replace_seal`, `stp_repressurize_verify`).
5. Smoke test: 1 pre-existing FAIL (BASE_KB fixture missing schema-required fields) — fix fixture or skip schema check in smoke context.

## State of files
- `render.py` — done.
- `promote.py` — done; bucket mode + mark_promoted + ADD draft/merge path wired.
- `storage.py` — done; single Supabase I/O layer.
- `draft_add.py` — done and smoked; OPENAI_API_KEY now in .env.
- `distill/tests/smoke_promotion.py` — 8/9 pass (1 pre-existing schema fixture issue).
