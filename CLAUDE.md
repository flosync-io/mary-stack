# Machine Mary — repo root

Three blocks around one contract. Nothing integrates them; `schema.json` does.

- **build/** — Mary herself: `mary.yml` → Dify. Consumes `knowledge.json`.
- **distill/** — messy sources → schema-conformant `knowledge.json`.
- **eval/** — Alex + scripted suite. Tests the deployed Mary against the same knowledge.

## Shared contract (true for every block)

- `knowledge.json` is the spine: produced by distill, consumed by build (runtime) and eval (ground truth). Governed by `contracts/schema.json`.
- A finding pins `mary_yml_version × knowledge_version × app_id` — no manifest, no finding.
- Every wrong move is **data / logic / prompt** → routes to distill / build·engine / build·prompts.
- A fault found live (B) gets promoted to a scripted scenario (A) so it can't silently regress.

## Memory protocol

At the start of a task, read `progress.md` and `notes.md` in the block you're working in (they don't auto-load; only CLAUDE.md does). When you wrap up, run the **update-memory** skill. Keep this file short — durable one-liners only.
