# Machine Mary

AI peer-trainer and troubleshooting assistant for CNC operators. This is a monorepo: three blocks that build, feed, and test Mary, held together by one shared contract.

## The three blocks, one contract

The blocks never call each other — they exchange **versioned files around one schema**.

- **build/** — Mary herself. Edit `mary.yml`, publish to Dify. Runs on `knowledge.json`.
- **distill/** — turn messy sources (PDFs, video, audio) into schema-conformant `knowledge.json`.
- **eval/** — Alex + the scripted suite. Talk to the deployed Mary, grade her against the same `knowledge.json`.

`knowledge.json` is the spine: **distill** produces it, **build** runs on it, **eval** grades against it. The full interface spec is in [`docs/BLOCK-CONTRACT.md`](docs/BLOCK-CONTRACT.md).

## Structure

```
mary-stack/
├── README.md
├── CLAUDE.md                  # root: shared contract, auto-loads every session
├── .gitignore
│
├── .claude/                   # shared agent config — committed, works on clone
│   ├── settings.json          #   hooks: SessionStart loads memory, SessionEnd logs a breadcrumb
│   ├── session-log.md         #   local breadcrumb (gitignored — not shared truth)
│   └── skills/
│       └── update-memory/     #   the skill that promotes progress → CLAUDE.md / notes.md
│           └── SKILL.md
│
├── contracts/                 # neutral shared surface (build + distill + eval all depend on it)
│   ├── schema.json            #   the knowledge-base contract  ← replace placeholder with the real one
│   ├── run-manifest.example.json
│   └── finding.example.json
│
├── knowledge/                 # the spine — distill's output, build + eval's input
│   └── <machine>.json         #   e.g. DMC80FD-01.json, carries _meta.version + sha256
│
├── build/                     # ── Block 1 ──────────────────────────────
│   ├── CLAUDE.md  progress.md  notes.md
│   ├── mary.yml               #   the Dify DSL
│   └── prompts/               #   SOUL + few-shots (single source of truth)
│
├── distill/                   # ── Block 2 ──────────────────────────────
│   ├── CLAUDE.md  progress.md  notes.md
│   └── ...                    #   the pipeline (graduated from the distill-knowledge skill)
│
├── eval/                      # ── Block 3 ──────────────────────────────
│   ├── CLAUDE.md  progress.md  notes.md
│   ├── alex/                  #   Key B — adversarial NL discovery
│   ├── scripted/              #   Key A — legacy mary-eval, moved in ~intact (runners/ results/ specs/ …)
│   ├── shared/                #   scorer · ledger · results writer · finding emitter
│   ├── scenarios.yml          #   the A-suite — grows by one entry per closed finding
│   └── findings/              #   Alex's output / draft queue
│
├── backend/                   # Supabase
│   └── supabase/
│       ├── functions/         #   edge functions (e.g. dify-proxy)
│       └── migrations/
│
└── docs/                      # cross-block
    ├── BLOCK-CONTRACT.md       #   the four shapes, the spine, the two rules
    ├── block-contract.html     #   one-screen visual of the same
    └── adr/                     #   architecture decision records
```

## The contract in one screen

1. **`knowledge.json`** (distill → build + eval), governed by `contracts/schema.json`. Carries `_meta.version` + `sha256` so it can be cited.
2. **run manifest** (build → eval): pins `mary_yml_version × knowledge_version × dify_app_id`. Mary's behaviour is that cross-product, so a test is only reproducible if it names the tuple.
3. **finding** (eval → build + distill): a verdict plus `fault_class ∈ {data, logic, prompt}` that routes the fix — **data → distill, logic → build·engine, prompt → build·prompts**.
4. **The loop:** a fault discovered live (Key B) gets fixed, re-run, then promoted into `scenarios.yml` (Key A) so it can never silently regress.

## Memory system

So anyone can clone and pick up where the last person left off — no install, all committed.

- **`CLAUDE.md`** auto-loads (root + the block you're in). Durable rules only; keep it short.
- **`progress.md`** per block — the churn: now / next / open questions.
- **`notes.md`** per block — the detail: why a decision was made, how a fix worked. Loaded on demand.
- **Hook** (`.claude/settings.json`): on session start it reminds you to read the block's `progress.md`/`notes.md` and prints the recent session log; on session end it appends a breadcrumb of what changed.
- **Skill** (`update-memory`): at wrap-up, sorts outcomes by altitude (durable → `CLAUDE.md`, why → `notes.md`, in-flight → `progress.md`), runs guardrail checks, and shows you what moved.

The only team habit required: say **"update memory"** when a task is done.

## Getting started

1. Clone the repo.
2. Open it in Claude Code and run `/hooks` once to review the committed hooks (config is snapshotted at session start).
3. Work inside the relevant block — `build/`, `distill/`, or `eval/`. Root + block `CLAUDE.md` load automatically; read that block's `progress.md` first.
4. When you finish a chunk, say **"update memory"** to promote it. Commit.

Anything shared across all three blocks (the contract, `schema.json`, version pinning) lives in the **root** `CLAUDE.md` and `docs/` — block files stay block-specific.
