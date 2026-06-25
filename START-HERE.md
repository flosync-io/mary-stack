# START HERE — Claude Code handoff

Planning happened in claude.ai (architect). You build with Claude Code. This is the bridge.

## 1. Park it (once)

```bash
# from the unzipped mary-stack/
git init
git add -A
git commit -m "Machine Mary monorepo: scaffold + plan + promotion loop (B-zero)"
```

Everything's already here: the three blocks, contracts, the `.claude/` memory + hooks, the plan docs, and the built promotion pieces. In Claude Code, run `/hooks` once to accept the committed session hooks.

## 2. What Claude Code reads first

These auto-load (CLAUDE.md, directory-walk) or are pointed to:
- `CLAUDE.md` (root) + `distill/CLAUDE.md` + `backend/CLAUDE.md` — the guardrails. **Loaded automatically.**
- `docs/adr/ADR-0001-knowledge-persistence.md` — the why (persistence, machine memory, mandatory fields).
- `distill/BUILD-PLAN.md` — the build order + done-when tests.
- `docs/2026-06-25-todays-plan.html` — the plan to read.

## 3. The kickoff prompt — paste this into Claude Code

> Read `CLAUDE.md`, `distill/CLAUDE.md`, `docs/adr/ADR-0001-knowledge-persistence.md`, and `distill/BUILD-PLAN.md`. We're building the B-zero promotion loop in `distill/`, leaf-first. Do **one step at a time** and stop at each done-when check for me to confirm before moving on.
>
> **Step 1 — `distill/render.py`.** Extract the human-render into one shared module: `narrate(runtime, knowledge) -> str` and `name_of(slug, knowledge) -> str`. Use the REAL runtime shape (see `distill/CLAUDE.md`) and the logic already in `view_runtime.py`. Lean on verbatim operator fields; resolve slugs via knowledge.json; humanize on miss; no LLM. **Done when** it reproduces the 3 narratives for `distill/sample/real-runtime/*.json` exactly (1 resolved coolant, 1 open-with-clarify press, 1 open spindle). Then have `view_runtime.py` import it (no duplicate slug logic).
>
> Wait for my OK, then:
> **Step 2 — `distill/promote.py`.** Re-point its reader OFF the old stub fields (`engine_evidence`/`chosen`/`sep`) ONTO the real shape (`status=="green"`, `matched_fm`, `confirmed_cause`, conv-id = filename). Route: green + `matched_fm` in knowledge → ENRICH (→ REVISE if `resolution_note` contradicts / escalated); `matched_fm` null → ADD; non-green → skip. Ground each change with `render.narrate()`. **Done when** `python3 promote.py --knowledge sample/knowledge-DMC80FD-01.json --runtime sample/real-runtime --out out` yields 1 ENRICH (coolant) and 2 skipped.
>
> Wait for my OK, then:
> **Step 3 — `review.html`.** Update the generator so each change card shows the `render.narrate()` story above the editable before→after, REVISE starts unchecked, and approve downloads a `_meta`-version-bumped `knowledge.json` + decision log. **Done when** I can approve a subset and get a valid versioned file.
>
> Guardrails (from CLAUDE.md): distillation generalizes, never appends; one writer to knowledge.json; `out/` is gitignored; never deploy/migrate Supabase without my sign-off. When each step is done, run the `update-memory` skill.

## 4. After the loop is green

Point Claude Code at the backend track (`backend/CLAUDE.md` + ADR-0001 action items), smallest-first:
1. Stamp identity/time at the proxy (`conversation_id, operator_id, source_app, created_at`) — **unblocks everything else.**
2. Repoint `get-machine` (keep its JSON shape; `memory_captured` ← `runtime.json.resolution_note`).
3. Extend `machines`; slim `vault`; drop `machine_memory`; add the error envelope.

Draft migrations and function diffs for review — **don't deploy without sign-off.**

## 5. The open questions to answer with real data (do early)
- Does N15 actually write `runtime/<machine>/<conv>.json` for recent convs? (pull one from the bucket)
- Who fires "resolve" — Dify confirmed-path flag, or the proxy on status flip?

Both are answered by inspecting one real bucket object + the Dify flow; they decide whether capture is "repoint a read" or "build it."
