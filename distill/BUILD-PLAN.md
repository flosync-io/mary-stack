# distill — promotion + review build plan (B-zero)

The whole promotion + review subsystem, where it lives, and the order to build it. B-zero: manual, git-versioned, no cache/recurrence/LLM. The pieces mostly exist — this is park, adapt to the real runtime shape, and wire the narrative into the review.

## Where it parks (Block 2 · `distill/`)

```
distill/
├── render.py            # slug→name + narrate() — the human view, SHARED
├── view_runtime.py      # runtime.json → plain sessions.html (imports render)
├── promote.py           # resolved runtime → candidate + review.html (imports render for grounding)
├── sample/
│   ├── knowledge-DMC80FD-01.json   # stub today → swap for the real one
│   └── real-runtime/*.json         # the 3 real resolved/open sessions
├── out/                 # generated review.html / sessions.html / candidate.json  (GITIGNORED)
├── README-promotion.md  BUILD-PLAN.md
└── CLAUDE.md  progress.md  notes.md   # block memory (already scaffolded)
```

Rules: `out/` is generated → gitignore it. The **approved** `knowledge.json` is committed up in `knowledge/<machine>.json` (that's the version store). `render.py` is the single source of human-rendering so the standalone viewer and the review grounding never drift.

## Build order

**1 · Park & baseline** *(~10 min, no code change)*
Drop `promote.py`, `view_runtime.py`, `sample/`, the README into `distill/`. Run both on the samples.
*Done when:* `out/review.html` and `out/sessions.html` both open and look right.

**2 · Adapt `promote.py` to the real runtime shape** *(first real code)*
It still expects the old stub fields (`engine_evidence`, `chosen`, `sep`). Switch to the real shape (already proven in `view_runtime.py`): resolved = `status == "green"`; route on `matched_fm` / `confirmed_cause`; conversation id = filename (since `id` is null); no `sep`. Routing: green + `matched_fm` in knowledge → **enrich** (→ **revise** if `resolution_note` contradicts / escalated); `matched_fm` null → **add**; non-green → skip.
*Done when:* `promote.py --runtime sample/real-runtime` → 1 ENRICH (coolant), 2 skipped (open).

**3 · Extract `render.py` + wire the narrative into `review.html`**
Pull `slug→name` + `narrate()` out of `view_runtime.py` into `render.py`; both files import it. Replace `review.html`'s field-list grounding with the **plain story** per change (the decision: the reviewer reads the session as prose, not slugs).
*Done when:* each ENRICH/ADD/REVISE card shows the human narrative above the editable object.

**4 · Swap in the real `knowledge.json`**
Pull `knowledge/DMC80FD-01.json` from the `mary-memory` bucket → `distill/sample/` (and up to `knowledge/`). Re-run.
*Done when:* slugs resolve to real names; enrich targets the real failure modes (not the stub).

**5 · Run on real resolved sessions**
Pull resolved (`status=green`) `runtime/<machine>/<conv>.json` from the bucket → a local dir → `promote.py --runtime <dir> --knowledge knowledge/DMC80FD-01.json`. (Manual pull until proxy capture lands.)
*Done when:* `review.html` is generated from real production sessions.

**6 · Real approve pass (Denver)**
He opens `review.html`, reads the stories, edits/skips, approves → downloads the version-bumped `knowledge.json` + decision log. Commit it.
*Done when:* a real promoted build is committed. `git revert` = rollback. Re-run `promote.py` anytime = rebuild from runtime.

## What to do first

**Step 1, then Step 2.** Park the files and run the baseline (proves the loop end-to-end on samples in minutes), then adapt `promote.py` to the real shape — that's the first real code and it unblocks everything after it. Don't pull real data (Steps 4–5) until 2–3 are green; debugging the loop on the 3 known sample files is faster than on live storage.

## Deferred (design unchanged, just unbuilt)
Proxy writes turns to Supabase · automated pull-from-bucket + cadence · `cache.json` + recurrence/auto-gate + async job · LLM-rendered narrative (Mary's Render seam per session) · publish approved build to Storage as `current`.
