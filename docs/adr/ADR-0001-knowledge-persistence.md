# ADR-0001: Knowledge persistence — vault, memory, runtime, cache, knowledge

**Status:** Proposed
**Date:** 2026-06-25
**Deciders:** Pranav (backend), Pushkar (founder); review: Saksham (frontend), Raj (evals)

## Context

Two persistence models had drifted into coexisting:

- **May (Sprint 2) — three Postgres tables:** `vault` (raw per-session record), `machine_memory` (curated per-machine knowledge), `operator_memory` (curated per-operator knowledge). Memory injected at session open; written back on resolve.
- **June (v5.1) — two Storage JSONs** (bucket `mary-memory`, project `kaxwnmsoxdrvgnlelafl`): `knowledge/<machine>.json` read at pipeline node N0; `runtime/<machine>/<conv>.json` written every turn at N15.

Forces:
- The June audit found `vault` diagnostic fields (`fault_type`, `steps_taken`, `ruled_out`) sitting NULL because they only wrote if the loop completed; `machine_memory` had 41 rows, all `fault_pattern`, with duplicate writes; old Dify apps were deleted, taking their transcripts with them (durability hole); and a split-brain where the thread list reads Supabase (`get_threads`) but message history live-reads Dify. `vault` and `machine_memory` were archived (`*_archive_20260625`) and truncated to 0; a `source_app` column was added to both (NULL = legacy era).
- Doctrine: behaviour = engine × `knowledge.json`; a wrong move must be attributable to data / logic / prompt. `knowledge.json` is depended on by both build and eval, so it cannot drift.
- Founder decision on file: field-resolved sessions write into curated knowledge with a `superseded_by` flag, **no human review gate**.
- Multi-machine is imminent; onboarding a machine should be a data operation, not a code change.

## Decision

Adopt the JSON model as the system of record and retire the curated table. Persist along a **three-tier granularity gradient**, write the contract through a **staged, gated promotion**, and make every knowledge change **versioned and reversible**.

**Tier model (granularity decreases upward):**

```
runtime/<machine>/<conv>.json   raw — every turn, full case          (the case files)
cache.json                      staged — distilled candidates        (the inbox; novel/conflicting only)
knowledge/<machine>.json        promoted — generalized, deduped truth (the contract / textbook)
```

**Table decisions:**
- `machine_memory` → **dropped as a table.** Its two jobs split cleanly: (1) *curated knowledge* → `knowledge/<machine>.json`; (2) the *per-machine incident logbook* (`day, issue, resolution`) → a **derived view**, not stored. Machine memory is built on read: filter the vault index to that machine's resolved (`green`) sessions, order by `created_at`, join each to its `runtime.json` (`reported` = issue, `resolution_note` = resolution). Always live, never drifts — a new resolved session *is* a new logbook entry. Expose via `get-machine` (already returns `sessions[]` ordered by `created_at`) or a read-only `machine_memory` SQL **view** — never a table. Archive retained; not rebuilt.
- `vault` → **kept but slimmed to a thin per-conversation index** — `(conversation_id pk, machine_id, operator_id, status, source_app, created_at, updated_at)`. It powers `get_threads`/thread-list (a query you cannot serve by scanning Storage blobs). The conversation **body** lives in `runtime.json`; the index only needs `status`.
- `operator_memory` → **kept as-is for now** (orphan: per-operator, cross-machine; fits neither machine JSON). Decision deferred: table vs `operator/<operator>.json`.

**Mandatory record fields — non-negotiable.** Every session record carries identity and time, on **both** the vault index and `runtime.json`. Today's real files fail this (`id` null, no `operator_id`, no timestamps) — closing it is a prerequisite, not a nice-to-have, because the logbook ("day") and reproducibility both depend on it:

| Field | Why it's required | Today |
|---|---|---|
| `conversation_id` (`id`) | the session key; logbook ⋈ runtime join | **null in runtime.json** — fix |
| `operator_id` | who; powers `get_threads`, operator scope | **absent** — fix (canonical key; reconcile from `user_id`) |
| `source_app` (app slug) | which Dify app produced it; provenance + registry | column exists on vault; populate |
| `created_at` (+ `resolved_at`) | the "day" — ordering + the logbook itself | **absent** — fix; logbook is exactly as good as this |
| `machine_id` (`machine`) | partition key | present |
| `knowledge_version` | which build Mary ran against; reproducibility | absent — add (nice-to-have) |

The **proxy is the natural writer** of these — it sees `conversation_id`, `operator_id` (from the session JWT), `machine`, and the app slug on every turn — so it stamps the vault index row even when Dify's N15 writes the runtime body.

**Promotion (resolve-time routing uses the engine's existing match result):**

```
resolve →
  clean match to existing FM AND resolution agrees   → DIRECT into knowledge.json (fast path)
  match BUT resolution contradicts the FM            → cache.json (supersede candidate, gated)
  no clean match / novel (chosen=null, below floor)  → cache.json (new-FM candidate, gated)
```

- Reuse the engine's own constants (`DECLINE_FLOOR = 0.45`, `TIE_BAND = 0.10`) as the fast-path gate. One set of constants, two jobs.
- **Direct (fast path) = provenance + evidence/recurrence increment only — never a content rewrite.** Any change to *what an FM says* goes through cache + gate.
- The async promotion job (deferred v5.2 #8) promotes cache candidates by novelty / recurrence / confidence / conflict.
- No human review gate — preserves the founder decision's intent; "write directly" becomes "direct-reinforce known faults, park novel/conflicting ones."

**Distillation generalizes, it never appends.** A resolved case updates or adds a *failure mode*; it never dumps the raw case into the contract. Granularity is `runtime.json`'s job.

**Versioning / rollback (layered):**
1. `superseded_by` — object-level soft correction (exists).
2. **Versioned immutable builds + a `current` pointer** — never overwrite `knowledge/<machine>.json` in place; each build is a new object (`_meta.version`, `parent_version`, `sha256`); `current` says which Mary reads. Whole-file rollback = move the pointer. **Do this now.**
3. **Append-only delta log keyed by `source_conversation_id`** — session-level undo (revert every delta from a bad conversation). `cache.json` is the staging buffer; the delta log is the upgrade. Target.
4. **Re-distill from `runtime.json`** — ultimate backstop; the substrate survives, so the contract is always rebuildable.

**System of record:** the versioned builds (+ delta log) are authoritative; mirror the `current` build to **git** (diffable) and publish to **Storage** for Mary's runtime read. Resolve **appends** (cache/delta); a compaction/publish step produces the next versioned build and moves the pointer. Runtime stays a simple read of `current`.

**Multi-machine:** `machine_id` is the partition key on every artifact (knowledge path, runtime path, vault index, cache, eval scope, finding manifest). Machine-neutral things (engine, `schema.json`, prompts, floors) stay one shared copy; machine-specific things (`knowledge/<m>.json`, `runtime/<m>/…`, registry row) are per machine. The identity registry (`BACKEND-PROBLEMS.md` solution 1) resolves slug → key. Onboarding machine N = registry row + `knowledge/<N>.json`. No engine/prompt change.

## Options Considered

### Option A: Keep the three Postgres tables (May model)
| Dimension | Assessment |
|-----------|------------|
| Complexity | Med |
| Cost | Cross-conversation SQL is easy; capture and durability are not |
| Scalability | Fine for rows; poor for durable transcripts |
| Team familiarity | High |

**Pros:** SQL analytics across cases; single-row atomic writes; familiar.
**Cons:** capture depended on loop completion (fields were NULL); curated table drifts from eval ground truth; transcripts tied to Dify app lifecycle (lost on delete); split-brain with live Dify history reads; duplicate-write quality rot.

### Option B: JSON tiers — runtime → cache → knowledge, vault as thin index (chosen)
| Dimension | Assessment |
|-----------|------------|
| Complexity | Med (new consistency + versioning model) |
| Cost | Durability and capture cheap; analytics deferred |
| Scalability | Per-machine partitioning is free |
| Team familiarity | Med (already half-built in v5.1) |

**Pros:** durable (survives Dify deletion); capture independent of resolution; one curated source of truth shared by build + eval; gated promotion kills dup-writes and shrinks blast radius; multi-machine free; git-diffable contract.
**Cons:** `knowledge.json` write contention; two-writer consistency (index in Postgres, body in Storage, no transaction); a bad distil sits upstream of the contract; lost cross-conversation queryability; `runtime.json` rewrite cost on the hot path.

## Trade-off Analysis

The whole decision is **rows → blobs + a thin index**. Tables win at concurrent writes and cross-record queries; per-conversation JSON wins at whole-record reads and durability. For a live troubleshooting product, capture-completeness and durability matter more than ad-hoc analytics, so B is right — but the two hot files (`runtime.json` per turn, `knowledge.json` per resolve) are where the risk concentrates, and the **cache + gated promotion** pattern is what defuses it: resolve appends to `cache.json` instead of read-modify-writing the live contract, so write-contention and bad-distil blast radius both shrink to the staging layer.

## Consequences

**Easier:** durability (Dify-independent); split-brain removed (history reads `runtime.json`); capture no longer needs a completed loop; one persistence model; single curated source of truth; dup-writes gone; multi-machine onboarding is data-only; known faults reinforce in real time (the compounding pitch).

**Harder / to engineer:**
- `knowledge.json` write contention → mitigated by cache + versioned builds + single compactor (no concurrent read-modify-write).
- Two-writer consistency (index Postgres + body Storage) → index = source of truth for *existence*; key `runtime.json` by `conversation_id` (idempotent); periodic orphan sweep.
- Bad distil upstream of the contract → cache gate + `superseded_by` + pointer rollback.
- Propagation latency: novel knowledge isn't visible until the promotion job runs → job cadence is a **product** decision (compounding feels laggy if too slow). Direct-reinforce path keeps the common case zero-latency.

**To revisit:** no analytical layer (cross-conversation SQL) — out of scope, name it; `operator_memory` orphan; raw record is now mutable (weaker audit than an append-only log — matters for AS9100-ish certifiability); permanent legacy gap (pre-`source_app` transcripts are gone).

## Live readers & backwards compatibility (verified 2026-06-25 against deployed functions)

Auditing the deployed edge functions changed the "just drop the tables" plan: `vault` and `machine_memory` have a **second live reader** beyond `get_threads`.

- **`get-machine`** reads `machines` (metadata) **+ `vault` (`select *`, the fat fields: `fault_type, heading, steps_taken, ruled_out`) + `machine_memory.content`** (returned as per-session `memory_captured`), and emits a machine-detail payload (info + session list + NL summary). So slimming `vault` and dropping `machine_memory` **break this screen unless `get-machine` is repointed.**
- **`machines` + `operators`** are the **already-built registries** (machines: `machine_id, name, oem, family, variant, description, location`; operators: CRUD keyed by `operator_id`). The `BACKEND-PROBLEMS.md` identity registry is therefore an **extension of `machines`** (`+ dify_app_key, knowledge_path, onboarded`), not a new table.
- **`get-onboarded-knowledge`, `get-research-knowledge`, `get-video-knowledge` are DEPRECATED** — the old raw-markdown knowledge surfaces. Out of scope: no repoints, no distill wiring. `knowledge.json` (curated, via the distill block) is the single knowledge surface going forward.
- **Drift:** `get-machine` filters `vault` by `user_id`; `get_threads` and the `operators` table use `operator_id`. Reconcile to `operator_id`.

**Rule: keep the interface, repoint the internals.** Hold the `get-machine` JSON shape and the `get_threads` envelope stable (the Flutter app depends on them); change what they read underneath. Concretely, `memory_captured` repoints from `machine_memory.content` → **`runtime.json.resolution_note`** (the per-session distillate's new home), and per-session detail repoints from fat `vault` columns → `runtime.json`. Shim only if an *unaudited writer* of the old shape turns up.

## Action Items
1. [ ] **Repoint `get-machine` BEFORE dropping `machine_memory` / slimming `vault`:** machine info from `machines` (unchanged); session detail from `runtime.json`; `memory_captured` ← `runtime.json.resolution_note`; drop the `machine_memory` join. Keep the response shape.
2. [ ] Extend `machines` with `dify_app_key, knowledge_path, onboarded` (don't build a new registry table); reuse `operators`. Reconcile `vault.user_id` → `operator_id`.
3. [ ] Slim `vault` to the index shape; keep `threads` view + `get_threads` on top.
4. [ ] Confirm `runtime/<machine>/<conv>.json` is actually being written by N15 for recent convs. **Note: runtime.json is engine STATE, not the transcript — turns are a separate capture (see ADR note).**
5. [ ] Add a `contracts/runtime.schema.json` and grow it: **required-now `id`, `operator_id`, `created_at` (+ `source_app`); when green, `resolved_at`**; nice-to-have `ruled_out`, match score, `knowledge_version`, escalation. Today's real shape lacks all of these and `id` is null.
6. [ ] **Machine memory = derived view, not table.** Build `(day, issue, resolution)` on read from vault-index (resolved, by `created_at`) ⋈ `runtime.json` (`reported`/`resolution_note`); expose via `get-machine` or a read-only SQL view. Requires `created_at` on the index.
7. [ ] **Stamp identity/time at the proxy:** on each turn, upsert the vault index row with `conversation_id`, `operator_id`, `machine_id`, `source_app`, timestamps. Non-negotiable — logbook + reproducibility depend on it.
8. [ ] Stop in-place writes to `knowledge.json`: `_meta` version chain (git = versions, revert = rollback); publish each approved build to Supabase Storage as Mary's runtime copy. Cache + builds + pointer deferred.
9. [ ] Promotion B-zero: `promote.py` (engine-state field-map) → `review.html` (narrative grounding) → human approve → versioned `knowledge.json`. Built; adapt extractor to the real runtime shape.
10. [ ] Record the founder-decision update: "direct write" → "direct-reinforce + park-and-promote, still no review gate."

> **runtime.json ≠ history source.** It holds engine state (`reported`, `checks`, `matched_fm`, `resolution_note`), not the verbatim turns. Distillation reads it; history display needs the turns (separate proxy capture). Don't assume the transcript lives in runtime.json.
