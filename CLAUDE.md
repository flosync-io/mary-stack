# Machine Mary — repo root

Three blocks around one contract. Nothing integrates them; `schema.json` does.

- **build/** — Mary herself: `mary.yml` → Dify. Consumes `knowledge.json`.
- **distill/** — messy sources + resolved sessions → schema-conformant `knowledge.json`.
- **eval/** — Alex + scripted suite. Tests the deployed Mary against the same knowledge.
- **backend/** — Supabase edge functions + migrations (the runtime/vault/registry plumbing).
- **voice-agents/** — local mirror of ElevenLabs conversational agents (Phil interviewers). Upstream source capture, outside the `knowledge.json` contract. See `voice-agents/CLAUDE.md` before pushing — live-push requires the user to say "yes push to prod".

## Persistence (ADR-0001 — read `docs/adr/` before backend or distill work)

- Storage: `mary-memory` bucket. `knowledge/<machine>.json` (curated, read at N0) + `runtime/<machine>/<conv>.json` (engine STATE, written every turn — not a transcript).
- `machine_memory` table = **dropped**; curated → `knowledge.json`; the `(day,issue,resolution)` logbook = a **derived view** over vault-index ⋈ runtime.
- `vault` = thin per-conversation index. Every record MUST carry `conversation_id, operator_id, source_app, created_at` (proxy stamps them).
- `knowledge.json`: one writer, `_meta` version chain, git = versions + `git revert` = rollback, published to Storage for Mary.
- Today's plan: `docs/2026-06-25-todays-plan.html`; build order: `distill/BUILD-PLAN.md`.

## Shared contract (true for every block)

- `knowledge.json` is the spine: produced by distill, consumed by build (runtime) and eval (ground truth). Governed by `contracts/schema.json`.
- A finding pins `mary_yml_version × knowledge_version × app_id` — no manifest, no finding.
- Every wrong move is **data / logic / prompt** → routes to distill / build·engine / build·prompts.
- A fault found live (B) gets promoted to a scripted scenario (A) so it can't silently regress.

## Memory protocol

At the start of a task, read `progress.md` and `notes.md` in the block you're working in (they don't auto-load; only CLAUDE.md does). When you wrap up, run the **update-memory** skill. Keep this file short — durable one-liners only.
