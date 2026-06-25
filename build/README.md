# build/ — Mary herself

Mary is a Dify advanced-chat flow: two LLM seams (Interpret, Render) wrap deterministic code (guard / engine / envelope). The IMD state machine — SANITY → MATCH → (CLARIFY) → DIAGNOSE → RESOLVE → VERIFY → CLOSEOUT — is all code; the LLM only understands and phrases.

## Layout
- `dify_yml/machine-mary-imd-chatflow.yml` — the deployable DSL and the **source of truth**. Engine code + prompts live inside it (v5.1 frozen).
- `dify_yml/tests/test_engine.py` — the regression gate. Extracts guard/engine/envelope from the yml and drives full conversations (16/16). No credentials; mocks the LLM seams via injected `scores`/`kind`. Run after every yml change.
- `HANDOFF-COMPLETE.md` — v5.1 architecture (12 nodes) + the v5.2 backlog.
- `prompts/` — reserved for extracted Interpret/Render prompts if/when prompts go git-native (v5.2).

## Workflow
1. Edit `machine-mary-imd-chatflow.yml` (here, not the Dify UI).
2. `python3 dify_yml/tests/test_engine.py` → 16/16.
3. Export/commit; a human imports to Dify (deploy needs sign-off).

## Consumes / produces
- Consumes `knowledge/<machine>.json` (read at N0) — same spine distill produces and eval grades.
- Produces `runtime/<machine>/<conv>.json` (written at N15) — engine state, the substrate distill promotes from.
