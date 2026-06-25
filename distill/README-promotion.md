# Promotion (B-zero) — runbook

The whole loop, manual, today. No cache, no recurrence counter, no LLM. Just: resolved runtime → distill → review page → approve → versioned knowledge.json.

## The three questions

**1. If I resolve a conversation, how does runtime get populated?**
It already is. `runtime/<machine>/<conv>.json` is written every turn — resolving doesn't *fill* it, it flips `_meta.status` to `resolved`. That status is the only thing that marks the file eligible for promotion. (Proxy-writes-turns is the v1 stretch; until then the file comes from Dify's N15, and you can also hand-feed any runtime.json to test promotion without live capture.)

**2. How do I run the promotion job?**
```bash
python3 promote.py \
  --knowledge knowledge/DMC80FD-01.json \
  --runtime   path/to/resolved/runtime/        # a file or a dir of them
  --out       out
```
It reads each resolved runtime.json, derives one proposed change, and writes `out/review.html` (+ `candidate.json`, `changes.json`). No LLM — it reads the engine's already-typed state (`chosen`, `sep`, `resolution`, `status`).

Routing (mirrors the engine's `DECLINE_FLOOR = 0.45`):
- `chosen` set and `sep ≥ 0.45` → **ENRICH** the matched failure mode (+provenance, +field note).
  - …flagged up to **REVISE** if the resolution looks like it contradicts existing guidance (e.g. "did not hold", escalated).
- `chosen = null` or `sep < 0.45` → **ADD** a new failure-mode candidate.

**3. How does Denver see it?**
He opens `out/review.html` — nothing to install. Per change he sees: the op (ADD / ENRICH / REVISE, **revises flagged ⚠**), where it came from (conversation, operator, symptom → resolution), the **before → after** of the actual object, and an **editable** box. He checks the ones to apply (revises start unchecked, on purpose), can rewrite any of them in place, types his name, and clicks **Approve & download**. Out comes the new `knowledge.json` + a decision log. Adds/enriches he skims; the ⚠ revise is the one he reads.

## Versioning & rollback

- On approve, the page **bumps `_meta`**: sets `parent_version` to the old version, writes a fresh `version`, and stamps `approved_by` / `approved_at`. So every build knows its parent — a version chain independent of git.
- **Commit `knowledge.json` to version it.** Git history *is* the version store at B-zero.
- **Roll back = `git revert`** (or restore the file named by `_meta.parent_version`). One file, clean undo.
- The substrate survives regardless: if a build is ever bad, the resolved `runtime.json` files still exist, so you can re-run `promote.py` and rebuild.

## Publish to where Mary reads (when capture is wired)
Mary reads `knowledge/<machine>.json` from Supabase Storage. After approve+commit, upload the approved file to the bucket as `current`. Until then, the git copy is the source of truth and the demo runs entirely on local files.

## Deferred (design unchanged, just unbuilt)
- Proxy writes turns to Supabase (v1 stretch).
- `cache.json` + recurrence/fingerprint counting; the auto-gate; the async/scheduled promotion job.
- LLM-assisted distillation (richer than the deterministic field-map v0).

## Try it now
```bash
cd distill
python3 promote.py --knowledge sample/knowledge-DMC80FD-01.json --runtime sample/runtime --out out
# open out/review.html, approve a couple, see the downloaded knowledge.json
```
