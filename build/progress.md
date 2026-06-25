# build — progress

## Now
v5.1 frozen. Repo setup: yml in dify_yml/, engine test in dify_yml/tests/, 16/16 green.

## Next
- v5.2 backlog (P0 no_answer; A6 QA-flag; A7 wrong-machine; clarify floor) — alongside ADR-0002 git-native engine extraction.

## Watch (drift hazards)
- Repo yml ↔ deployed Dify: export after any change; never author in the UI only.
- yml env-var knowledge ↔ repo knowledge/<machine>.json: keep single-sourced.

## Notes
- Engine + prompts live inside the yml today. Tests extract-and-run (real logic, not a copy).
