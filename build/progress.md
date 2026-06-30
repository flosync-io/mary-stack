# build — progress

## Now
Unreachable-DECLINE deadlock fixed (branch pp/dev/fix-engine-decline, commit 5f42394): deterministic `__none_of_these__` escape appended to every clarify MCQ; selecting it burns a clarify slot → DECLINE at CLARIFY_CAP. 19/19 green. Awaiting export to Dify.

Vault write path fully wired and validated against live eval (capture string confirmed). Awaiting export to Dify and vault table migration.

Unknown-fault eval sweep (2026-06-26, 10 scenarios, live DMC80FD-01) confirms the `__none_of_these__` escape + DECLINE-on-cap are ALREADY live in deployed Dify — so our pp/dev/fix-engine-decline branch is a repo/test hardening of already-deployed behavior, not new behavior. Abstention rated honest-and-quick; safety 10/10. Full findings in eval/notes.md.

## Next
- Export updated yml to Dify (deploy gate: human imports after test pass) — carries clarify-escape refactor + vault-write changes.
- Verify vault table exists in Supabase with columns: `conversation_id` (PK), `machine_id`, `operator_id`, `status`, `fault_type`, `resolution`, `created_at`, `updated_at`.
- **Eval-found bugs (higher leverage than the floor):** (1) compound/no-match decline writes empty `capture` (`"handoff: no-match; ruled out: "`) — downstream tech gets no symptom record; populate from `case.reported`/sanity_notes. (2) post-terminal status regression — a terminal `escalated` thread reopens to `diagnosing` and loops generic "Didn't catch that" reask under pressure (the `terminal=True`-doesn't-close behavior; needs a terminal latch or held-decline reask).
- v5.2 backlog (P0 no_answer; A6 QA-flag; A7 wrong-machine redirect — eval #4 confirms it's unbuilt; clarify plausibility-floor — eval rates it MODERATE polish, not urgent: escape already prevents wrong-procedure/slog) — alongside ADR-0002 git-native engine extraction.

## Watch (drift hazards)
- Repo yml ↔ deployed Dify: export after any change; never author in the UI only.
- yml env-var knowledge ↔ repo knowledge/<machine>.json: keep single-sourced.

## Notes
- Engine + prompts live inside the yml today. Tests extract-and-run (real logic, not a copy).
