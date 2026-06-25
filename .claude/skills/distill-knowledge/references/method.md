# Distill Knowledge — method

The reasoning behind the loop in SKILL.md. Read the section you need; you don't need all of it every run.

## Contents
- The fold loop, precisely
- Deriving a schema from an example instance
- The provenance & confidence model
- Merge semantics: add / enrich / revise
- Grounding discipline
- Referential integrity & validation patterns
- Blind regeneration (auditing an existing KB)
- The cold-start invariant pattern

## The fold loop, precisely

The skill is a reduce over input batches that accumulates one clean state:

```
state_0   = {}                              (or the schema's empty collections)
state_n   = distill(state_{n-1}, bundle_n, schema)
```

Properties worth protecting:

- **The schema is a stable interface** between messy inputs and clean state, so the state never drifts in shape.
- **Monotonic, roughly idempotent.** New material adds or refines; re-feeding the same bundle should not move the state. If it does, the merge is non-deterministic — usually a sign you keyed on something unstable instead of a real id.
- **Provenance enables legitimate overwrite.** Without a trust tier you can't tell a correction from a regression. With one, a higher-tier source revising a lower-tier value is correct behaviour, not data loss.
- **Distillation ≠ runtime.** Keep the *knowledge* in the JSON and keep *runtime/operational* concerns (control flow, signals, weights) out of it. A schema for knowledge should not try to model the system that consumes the knowledge.

## Deriving a schema from an example instance

When the user has an agreed example but no formal schema, derive one (JSON Schema Draft 2020-12):

- One `$def` per entity type; a root that holds the entity collections (arrays) plus an optional `$meta`.
- Model shared sub-objects once (e.g. a polymorphic reference object) and `$ref` them.
- Set `required` to the genuinely load-bearing fields; leave the rest optional. Be honest — over-requiring breaks real data.
- Use `additionalProperties: false` to catch drift, **but** allow annotation fields: add `"patternProperties": { "^\\$": {} }` so `$`-prefixed notes (`$note`, `$meta`, etc.) are permitted everywhere.
- Encode enums and numeric bounds you can see in the example (status values, 0–10 scores, etc.).
- Validate the example against the derived schema, then run **negative tests** — confirm the schema actually rejects out-of-range values, bad enums, unknown fields, and missing required fields. A schema that accepts everything is verifying nothing.
- When the contract evolves (a field gets promoted from optional to required, or a new block is added), re-validate the example and sync it if needed so the contract and its canonical example never disagree.

## The provenance & confidence model

Two orthogonal tags on facts:

- **provenance** — *where it came from* (e.g. `plant` / `oem` / `research`, or your domain's equivalents). Trusted tiers can ground authoritative values; the lowest tier (open research/lore) should **never** ground a hard value like a code or measurement.
- **confidence** — *how sure* (e.g. `high` / `med` / `low`). Low-confidence entries are reference-only: they enrich realism but must not drive decisions the schema treats as authoritative.

Keep raw, unaggregated records out of the trusted state until validated; let provisional records inform "what exists / what's in demand" without letting them drive authoritative rankings or selections.

## Merge semantics: add / enrich / revise

For each extracted entity, decide against the current state:

- **Add** — no existing entity covers this concept → insert it, with fresh ids in the project's id style; wire its refs.
- **Enrich** — an entity exists but the new source adds grounded detail → augment fields (append a code, add an alias, fill a previously-deferred value). Do not duplicate the entity.
- **Revise** — the new source contradicts an existing value → overwrite **only if** its provenance is at least as high; record that it changed.

Conflict rules:
- Higher provenance wins automatically.
- Equal provenance + genuine contradiction → do **not** pick silently. Keep the incumbent, flag the conflict in the diff/report, and let the human decide.
- Match entities by stable identity (a real `id` or a canonical concept key), never by surface wording that shifts between sources.

## Grounding discipline

- **Real values only.** Any code/number/identifier that should come from a source must appear verbatim in a source you can cite. Prefer the primary document over an excerpt of it.
- **Defer the unknowable.** For value-ranges that are owner/builder-specific or not in your sources, use a clearly non-numeric placeholder (e.g. `"<builder band — machine-specific; defer>"`), never a fabricated number.
- **Excerpt vs. manual.** A trimmed excerpt will make a from-scratch pass under-cover. If coverage matters, feed the full primary source as the grounding input, not the excerpt.
- **No invented parameters.** Never synthesize tolerances, offsets, settings, dosages, prices, or other operational numbers to fill a gap.

## Referential integrity & validation patterns

After schema validation, run the integrity checks the schema implies:

- **Refs resolve.** Collect every `id` in the state into a set; for each reference field (`*_ref`, id-lists, discriminator keys), assert the target exists.
- **Source-grounding.** For each constrained value, confirm it appears in the cited source text. A tiny script that greps the source corpus for each code/number is faster and more reliable than eyeballing.
- **Domain invariants.** Encode any "always true" rule the schema can't (e.g. cold-start counts must be zero, safety entities must escalate). Check them in a script so they're cheap to re-run.

## Blind regeneration (auditing an existing KB)

To test how good an existing distilled JSON is, rebuild a fresh one from raw sources **only** — blind to the existing JSON and to any prior extractions — then diff. The misses and additions tell you what the existing build over- or under-covers. Keep the regeneration honest: decide up front exactly which inputs count as "raw," and don't open the target file until the diff step. If the fresh pass under-covers a region, check whether it was starved of a primary source the original build had.

## The cold-start invariant pattern

A freshly built KB has no history. Encode that explicitly rather than leaving fields absent: counts at `0`, "last seen" at `null`, source pointers `null`, approvals `pending`, and any learned ranking left at its authored prior. Explicit zeros/nulls validate cleanly and make the "no data yet" state unambiguous — and they make the first real diff meaningful.
