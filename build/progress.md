# build — progress

## Now
Unreachable-DECLINE deadlock fixed (branch pp/dev/fix-engine-decline, commit 5f42394): deterministic `__none_of_these__` escape appended to every clarify MCQ; selecting it burns a clarify slot → DECLINE at CLARIFY_CAP. 19/19 green. Awaiting export to Dify.

Vault write path fully wired and validated against live eval (capture string confirmed). Awaiting export to Dify and vault table migration.

## Next
- Export updated yml to Dify (deploy gate: human imports after test pass) — now carries clarify-escape + vault-write changes.
- Verify vault table exists in Supabase with columns: `conversation_id` (PK), `machine_id`, `operator_id`, `status`, `fault_type`, `resolution`, `created_at`, `updated_at`.
- v5.2 backlog (P0 no_answer; A6 QA-flag; A7 wrong-machine; clarify floor) — alongside ADR-0002 git-native engine extraction.

## Watch (drift hazards)
- Repo yml ↔ deployed Dify: export after any change; never author in the UI only.
- yml env-var knowledge ↔ repo knowledge/<machine>.json: keep single-sourced.

## Notes
- Engine + prompts live inside the yml today. Tests extract-and-run (real logic, not a copy).
