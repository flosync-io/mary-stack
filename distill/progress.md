# distill — progress

## Now
promote.py is done and tested. Ready to run --apply on real resolved sessions.

## Next
1. Run `promote.py --knowledge knowledge/DMC80FD-01.json --runtime <real-runtime-dir> --apply` on all resolved sessions. Review dry-run diff, then re-run with --apply. Commit the versioned knowledge.json.
2. ADD stubs that come back "deferred — needs authoring" need human authoring (component_ref, title, guardrail, etc.) before they can be written.
3. Investigate N15 runtime write reliability (or move capture to proxy).
4. Who fires "resolve" / sets status=resolved?

## Open questions
- Does N15 write runtime.json reliably (or move capture to proxy)?
- Who fires "resolve"?

## State of files
- `render.py` — done; narrate() + name_of() single-sourced here.
- `promote.py` — done; dry-run default, --apply writes, ADD deferred if schema-incomplete.
- `distill/tests/smoke_promotion.py` — 8/9 pass (1 pre-existing: smoke test BASE_KB uses simplified FMs that don't carry schema-required fields).
- `sample/knowledge-DMC80FD-01.json` — stub; use `knowledge/DMC80FD-01.json` for real runs.
- `knowledge/DMC80FD-01.json` — real curated knowledge; ran promote dry-run on 0e62ec9a (1 ENRICH ready).
