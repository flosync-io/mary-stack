# Machine Mary — three-block dev contract

How the three dev blocks communicate so the build/iterate loop closes. Drafted 2026-06-23, ahead of the repo-layout conversation. This is the *interface* spec, not the repo. Handoffs may be manual; the **shapes** below are not negotiable.

## The one idea

The blocks do not call each other. They exchange **versioned files around one schema**. So "the contract" is four things: one schema, three boundary artifacts, a version-pinning rule, and a routing rule. Get those fixed and the blocks can be built, run, and even handed off by hand without drifting.

```
                 schema.json  (the contract both 1 & 2 obey)
                      │
        ┌─────────────┴──────────────┐
        ▼                            ▼
  ┌───────────┐  knowledge.json ┌───────────┐
  │ BLOCK 2   │────────────────▶│ BLOCK 1   │
  │ distill   │   (truth)       │ build Mary│
  │ (skill)   │────────┐        │ → mary.yml│
  └───────────┘        │        │ → Dify    │
        ▲              │ knowledge.json      └─────┬─────┘
        │              ▼  (ground truth)           │ run manifest
        │        ┌───────────┐◀────────────────────┘ (the tested tuple)
        │        │ BLOCK 3   │
        │        │ Alex eval │
        └────────│ (skill)   │
   finding:data  └───────────┘
                   │      │
        finding:logic    finding:prompt
                   ▼      ▼
               BLOCK 1 (engine / prompts)
```

`knowledge.json` is the spine. Block 2 produces it; Block 1 runs on it; Block 3 grades against it. A wrong answer is wrong relative to it.

## The shared schema (1)

`schema.json` is the knowledge-base contract. It is a dependency of **both** Block 1 (engine + fact-gate assume its shape) and Block 2 (distill targets it), so it belongs to neither — it sits in a neutral `contracts/` surface both import. Changing it is a contract change: it forces a re-distill (Block 2) and may move the fact-gate/engine (Block 1). Version it; a bump invalidates downstream artifacts.

## The three boundary artifacts

### A. `knowledge.json` — Block 2 → Block 1 and Block 3

Already governed by `schema.json`. The only thing the *contract* adds is that it must be **citable**: stamp a version so a run can name exactly which knowledge it tested.

```json
{
  "_meta": { "machine": "DMC80FD-01", "version": "2026-06-23.a", "schema": "1.x", "sha256": "<hash>" },
  "...": "failure_modes / checks / procedures / steps / warnings / never_do ..."
}
```

`version` + `sha256` are the citable handle. Live copy stays at Supabase `knowledge/<machine>.json`; the hash is what Block 3 records.

### B. run manifest — Block 1 → Block 3

The keystone. **Mary's behaviour = engine(`mary.yml`) × `knowledge.json`.** It is a cross-product, so a test is only reproducible if it pins *both* sides plus the deployed target. Block 1 writes this at publish; Block 3 cannot run without one.

```json
{
  "mary_yml_version": "v5.1",
  "knowledge_version": "DMC80FD-01@2026-06-23.a",
  "dify_app_id": "1d5aed45-1715-47cb-bbfd-34869cb45889",
  "schema_version": "1.x",
  "published_at": "2026-06-23T..."
}
```

### C. finding record — Block 3 → Block 1 / Block 2

This is what actually **closes the loop**. It is not a new format: it is the v5.2 backlog item (`title · severity · source · where · verify`) emitted by Alex instead of hand-written, plus the one field that routes it.

```json
{
  "finding_id": "f-2026-0623-007",
  "scenario": "A7-wrong-machine",        // from scenarios.yml (A) or an NL run (B)
  "run": { "mary_yml": "v5.1", "knowledge": "DMC80FD-01@2026-06-23.a", "app_id": "1d5aed45..." },
  "verdict": "fail",                      // pass | fail | flag
  "fault_class": "logic",                 // data | logic | prompt  ← the router
  "where": "engine MATCH — bunched tested before plausibility floor",
  "evidence": "press-jam scored all-near-zero; offered 3 CNC modes; sep=0.0, chosen=null",
  "expected": "DECLINE / redirect",
  "severity": "P1",
  "status": "draft"                       // draft → (human gate) → filed → fixed → closed
}
```

`fault_class` and `status` are the two load-bearing fields. Everything else is the issue body you already write by hand.

## Rule 1 — version pinning (reproducibility)

Every finding cites a `run` manifest. No manifest, no finding. This is the only reason the loop is *reproducible* rather than anecdotal: "Mary failed A7" is meaningless; "Mary `v5.1 × DMC80FD-01@2026-06-23.a` failed A7" can be re-run after a fix and shown to pass.

## Rule 2 — fault routing (attributability)

The handoff's own maxim — *every wrong move is attributable to data, logic, or prompt* — is not just for debugging. It is the **router** that sends a finding to the block that owns the fix:

| `fault_class` | Means | Goes to |
|---|---|---|
| `data` | knowledge.json is wrong/missing (e.g. an alarm not in the safety surface) | **Block 2** — re-distill / correct, bump `version` |
| `logic` | engine made a bad move on correct data (e.g. bunched-before-floor) | **Block 1** — engine code + a new `test_engine.py` case |
| `prompt` | Interpret mis-typed or Render mis-phrased | **Block 1** — the LLM seam + few-shots |

If Alex can tag the class, it doesn't just *score* Mary — it *assigns* the bug. That tag is the difference between three projects sharing a channel and one system.

## Rule 3 — B discovers, A pins (the loop actually closing)

This is the whiteboard's `A = scenarios.yml / B = NL` and `mary-eval`'s two modes, doing one job:

1. **B (live NL role-play)** explores and *discovers* a fault → emits a finding.
2. The finding routes by `fault_class`, gets fixed, version bumped.
3. The fix is re-run live to confirm (`status: fixed`).
4. **The discovering scenario is promoted into `scenarios.yml` (A)** as a permanent scripted regression. `status: closed`.

A fault can be found once by exploration but must be guarded forever by a script. The loop is closed only when a fixed fault has a scenario in A that fails if it ever comes back. (Per the handoff: human-gate the draft→filed step; only scripted A-mode regression is safe to run unattended.)

## Manual vs fixed

| Step | May be manual | Must be fixed (the contract) |
|---|---|---|
| Run distill, publish Mary, triage findings→issues | ✓ | — |
| `schema.json` shape | — | ✓ |
| `knowledge.json` carries `version`+`sha256` | (copy-paste ok) | ✓ field must exist |
| run manifest written at publish | (copy-paste ok) | ✓ all 5 fields |
| finding carries `fault_class` + `run` | — | ✓ |
| fixed fault promoted to `scenarios.yml` | ✓ (human writes the scenario) | ✓ that it happens |

The discipline is small: stamp versions, write a manifest at publish, tag findings, promote fixes. Everything else can stay hands-on until it hurts.

## Minimal file set the repo must hold

- `contracts/schema.json` — shared, neutral
- `contracts/run-manifest.example.json`, `contracts/finding.example.json` — the two shapes above
- per-machine `knowledge/<machine>.json` with `_meta`
- `scenarios.yml` (A) — grows by one entry per closed finding
- `findings/*.jsonl` — Alex output, the draft queue

Four shapes, one spine, two rules. That is the whole contract.
