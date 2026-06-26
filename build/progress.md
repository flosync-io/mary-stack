# build — progress

## Now
v_resolution fallback logic complete (resolution_note → reconstructed capture → ""). Vault write path fully wired.
Next: export yml to Dify (human step); verify/create vault table migration in backend/.

## Next
- Export updated yml to Dify (deploy gate: human imports after test pass).
- Verify vault table exists in Supabase with columns: `conversation_id` (PK), `machine_id`, `operator_id`, `status`, `fault_type`, `resolution`, `created_at`, `updated_at`.
- v5.2 backlog (P0 no_answer; A6 QA-flag; A7 wrong-machine; clarify floor) — alongside ADR-0002 git-native engine extraction.

## Watch (drift hazards)
- Repo yml ↔ deployed Dify: export after any change; never author in the UI only.
- yml env-var knowledge ↔ repo knowledge/<machine>.json: keep single-sourced.

## Notes
- Engine + prompts live inside the yml today. Tests extract-and-run (real logic, not a copy).
