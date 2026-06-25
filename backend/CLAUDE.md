# backend/ — Supabase (edge functions + migrations)

Read ADR-0001 (`../docs/adr/`) "Live readers" + "Mandatory record fields" before touching tables.

## Durable rules
- **Keep the interface, repoint the internals.** `get-machine`'s JSON shape and the `get_threads` envelope are contracts the Flutter app depends on — never change their output; change what they read underneath.
- **Repoint `get-machine` BEFORE dropping `machine_memory` / slimming `vault`.** It reads `machines` + fat `vault` + `machine_memory`. New sources: session detail ← `runtime.json`; `memory_captured` ← `runtime.json.resolution_note`; drop the machine_memory join.
- **Registries already exist** — `machines`, `operators`. Extend `machines` (`+ dify_app_key, knowledge_path, onboarded`); reuse `operators`. Don't build new registry tables.
- **`machine_memory` is a DERIVED VIEW, not a table** — `(day, issue, resolution)` = vault-index (resolved, by `created_at`) ⋈ `runtime.json`. Read-only view or `get-machine`; never resurrect the table.
- **Mandatory record fields (non-negotiable):** every session record carries `conversation_id`, `operator_id`, `source_app`, `created_at` (+ `resolved_at` when green). The **proxy stamps these** per turn onto the vault index. Reconcile `vault.user_id` → `operator_id`.
- **Deprecated — ignore:** `get-onboarded-knowledge`, `get-research-knowledge`, `get-video-knowledge`.
- Error envelope (no silent-empty): 404 `machine_not_onboarded` · 404/422 `operator_not_found` · 401 `unauthenticated` · 502 `upstream_error`.
- **Never deploy/migrate without explicit sign-off.** Draft migrations and function diffs; a human applies them.

Memory: read ./progress.md and ./notes.md at task start; run update-memory at task end.
