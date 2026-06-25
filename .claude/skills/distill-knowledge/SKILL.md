---
name: distill-knowledge
description: >-
  Distill messy source bundles (zips/folders of raw notes, transcripts,
  primary-source PDFs/manuals, research files) into one schema-conformant knowledge
  JSON, and fold later bundles into that same JSON over time. Use whenever the user
  has a JSON Schema acting as a knowledge-base contract plus corpora to structure, or
  an existing distilled JSON to extend, correct, or re-ground with new sources.
  Triggers: "distill this corpus", "turn these docs into the schema", "build/update
  the knowledge JSON", "merge this zip into the json", "add this to 2.json",
  "regenerate and diff", "derive a schema from an example", "diff two knowledge
  JSONs". Enforces provenance/confidence tagging, never fabricates codes or values,
  defers what it can't ground, keeps references resolving, validates against the
  schema, and emits a diff. Handles cold builds and incremental merges. Not for
  one-off summaries with no schema or persisted output.
---

# Distill Knowledge

Turn messy, mixed-trust source material into one clean, schema-valid knowledge JSON, and keep that JSON correct as new sources arrive. The whole skill is a single disciplined loop run over and over; this file is the loop, `references/method.md` is the reasoning behind each step.

## The mental model (read this first)

Three roles, and they never blur:

- **The schema is the contract** — a fixed point. It defines the shape, allowed values, and invariants. It does **not** change when new material arrives; everything else must conform to it. If the user only has an example instance and no schema, derive one first (see `references/method.md` → "Deriving a schema from an example").
- **The distilled JSON is the accumulated state** — the single source of truth, always schema-valid. It is *not* a transcript of the inputs; it is the structured residue of them.
- **Each bundle (zip/folder) is an input batch** — raw or primary-source material carrying some provenance (e.g. plant / OEM / research) and confidence (high / med / low).

The operation is a fold: `state' = distill(state, bundle, schema)`. A new bundle is **folded into** the existing state, not used to regenerate it from scratch. So "read the JSON, edit it, add to it" is exactly the job.

## Two modes

- **Cold build** — no prior JSON. Start from empty state and produce the first distilled file.
- **Incremental merge** — a JSON already exists. Load it as the starting state and fold the new bundle in. This is the common case after the first run.

(A third, optional mode — **blind regeneration** — rebuilds fresh from raw sources *only*, ignoring the existing JSON, purely to audit it by diffing. See `references/method.md`.)

## Invariants that must hold on every run

These are the point of the skill; hold them even when the user is in a hurry.

- **Conform to the schema.** The state is always schema-valid. Run the validator before declaring done.
- **Provenance + confidence are first-class.** Tag every fact with where it came from and how trusted it is. This is what lets a later authoritative source legitimately override an earlier guess.
- **Never fabricate.** Do not invent codes, IDs, part numbers, measurements, or any value that should come from a source. If a value should exist but isn't grounded, leave a labelled placeholder and defer it — never a plausible-looking number.
- **Prefer primary sources for ground-truth values.** An excerpt or a forum note can *suggest*; the manual/datasheet *grounds*. (Hard-won lesson: regenerating against a trimmed excerpt under-covers; regenerate against the full primary source.)
- **Keep references resolving.** Every cross-reference (`*_ref`, id lists, discriminators) must point at something that exists in the state.
- **Surface conflicts; don't silently resolve them.** When a new source contradicts the state and provenance doesn't cleanly decide, flag it for the human. The human owns the judgment the schema can't encode.
- **End every run with validate + diff.** No run is "done" until the file validates and you've reported what changed.

## The workflow

Work through these in order. Use a task list for anything beyond a trivial single-file merge.

### 1. Establish the contract
Locate the schema. If there's only an example instance, derive a JSON Schema from it first (`references/method.md` → "Deriving a schema from an example"), then proceed. Read the schema so you know the entities, required fields, enums, and invariants you must honor.

### 2. Inventory the bundle
Extract the zip/folder and classify every file by its role — don't treat them all alike:

- **Raw inputs** — unstructured material to extract from (notes, transcripts, research write-ups).
- **Primary-source ground truth** — authoritative docs (manuals, datasheets, standards) that ground specific values. Prefer these for any value the schema marks as needing a real source.
- **Already-structured records** — prior extractions to merge/validate, not re-derive.
- **Out of scope** — binaries (media, images), build scripts, orientation docs. Referenced, not distilled into the JSON.

A quick `find`/`unzip -l` and a per-file one-line characterization is enough. Record which files are ground truth for which fields.

### 3. Load state
Incremental mode: read the existing JSON — that is your starting point. Cold mode: start from an empty object with the schema's collections.

### 4. Ground & extract
Read the sources and extract entities that fit the schema. As you go: tag provenance + confidence; ground every constrained value (codes/numbers/IDs) against a primary source and never invent one; defer anything you can't ground with a labelled placeholder. Keep operator/author wording where the schema wants verbatim aliases or phrases.

### 5. Merge into state
Fold extracted entities into the JSON as one of three operations (detail in `references/method.md` → "Merge semantics"):

- **Add** — a genuinely new entity.
- **Enrich** — augment an existing entity with newly grounded detail.
- **Revise** — correct an existing entity when a higher-provenance source overrides it.

Higher provenance wins; equal-provenance conflicts get surfaced. Re-feeding the same bundle should not change the state (rough idempotence). Keep all refs resolving as you go.

### 6. Validate
Run the bundled validator against the schema and fix until clean:

```bash
python scripts/validate.py <schema.json> <state.json>
```

It validates collections-of-arrays files against the root schema, and one-example-per-key files per `$def`. Then run the domain checks the schema implies — referential integrity (all refs resolve) and source-grounding (every constrained value traces to a source). `references/method.md` shows the patterns.

### 7. Diff & report
Compare the new state against the prior state (incremental) or against a reference build (audit):

```bash
python scripts/diff_kb.py <old.json> <new.json>
```

Then write a short report: counts per collection, what was added / enriched / revised, what a from-scratch pass would recover / miss / add (if auditing), grounding results, and — most important — any conflicts left for the human to decide. Lead with a 3–4 line verdict.

## Bundled resources

- `scripts/validate.py` — general JSON-Schema validator (Draft 2020-12). Handles both array-collection files and singular one-example-per-key files; also meta-schema-checks the schema itself.
- `scripts/diff_kb.py` — general structural diff of two knowledge JSONs by collection and `id`: counts, added/removed ids, and which fields changed on matched ids.
- `references/method.md` — the reasoning layer: the fold loop, deriving a schema from an example, the provenance/confidence model, merge semantics, grounding discipline, blind-regeneration auditing, and the cold-start invariant pattern. Read it when a step needs more than the summary above.
