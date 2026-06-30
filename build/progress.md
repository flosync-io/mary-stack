# build — progress

## Now
`pp/dev/fix-engine-decline` MERGED to main (PR #2): `__none_of_these__` clarify escape + runtime schema + create-sample skill.

Active branch `pp/dev/engine-improvements` (off main) carries the MATCH-stage improvements, 27/27 green, NOT yet exported to Dify:
- (A) sanity detail folds into `reported` verbatim (commit b8845a0).
- ELICIT loop: vague low-score → probe instead of DECLINE; behavioral tapped-out stop (commit 2829895).
- `elicit_attempts` DSL wiring fix (6 sites) — first import returned empty engine output because only the code was edited; now mirrors `clarify_attempts`. Re-import will work.
- MATCH re-gated FLOOR-FIRST: floor tested before bunched, so bunched-but-all-below-floor → ELICIT (was wrongly CLARIFY-ing a menu of disbelieved candidates). **This closes the v5.2 "clarify plausibility-floor" backlog item.**

## Next
- Export `pp/dev/engine-improvements` yml to Dify (deploy gate: human imports after test pass) — carries (A) sanity-fold + ELICIT + the elicit_attempts wiring.
- **Still-open eval bugs:** (1) compound/no-match DECLINE writes empty `capture` (`"handoff: no-match; ruled out: "`) — populate from `case.reported`/sanity_notes ((A) makes `reported` richer now, but the capture string itself still isn't wired to it). (2) post-terminal status regression — terminal `escalated` reopens to `diagnosing` and loops "Didn't catch that" under pressure; needs a terminal latch.
- Alarm-code widening (codes typed in the sanity turn): now nearly free — (A) already routes such a code into `reported` so the deterministic regex catches it; add a test before claiming done.
- Verify vault table exists in Supabase with columns: `conversation_id` (PK), `machine_id`, `operator_id`, `status`, `fault_type`, `resolution`, `created_at`, `updated_at`.
- v5.2 backlog (P0 no_answer; A6 QA-flag; A7 wrong-machine redirect — eval #4 confirms it's unbuilt; clarify plausibility-floor — eval rates it MODERATE polish, not urgent: escape already prevents wrong-procedure/slog) — alongside ADR-0002 git-native engine extraction.

## Watch (drift hazards)
- Repo yml ↔ deployed Dify: export after any change; never author in the UI only.
- yml env-var knowledge ↔ repo knowledge/<machine>.json: keep single-sourced.

## Notes
- Engine + prompts live inside the yml today. Tests extract-and-run (real logic, not a copy).
