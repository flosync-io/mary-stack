---
name: update-memory
description: Update the per-block memory bank (CLAUDE.md / progress.md / notes.md) at the end of a task. Use when the user says "update memory", "wrap up", "log progress", or when a meaningful chunk of work just finished.
---

# update-memory

Keep the memory bank current and tidy so any of the three of us can clone the repo and pick up exactly where the last person left off. The hook captures a raw breadcrumb; this skill does the thinking.

## 1. Figure out which block

Work out which block this session touched — `build/`, `distill/`, or `eval/` — from the files changed and the conversation. If it spans more than one, update each. If it's genuinely repo-wide (the block contract, schema.json, version-pinning rule), that goes in the **root** `CLAUDE.md`, not a block file.

Read `.claude/session-log.md` (the hook's breadcrumb) only as a hint for what changed. The conversation is the real source.

## 2. Sort every outcome by altitude

For each thing that happened, decide where it belongs:

- **Durable rule or decision** (true from now on, e.g. "field-resolved sessions write straight to curated knowledge, no review gate") → one line into that block's `CLAUDE.md`.
- **Rationale / how a fix worked / why we chose X** → a short entry in that block's `notes.md`.
- **Still in flight** (current focus, next steps, open questions) → stays in `progress.md`.

Then reset `progress.md` so it only holds what's next — move anything finished out.

## 3. Guardrails (the "keep it in check" part — do these every run)

- Keep each `CLAUDE.md` short — aim under ~200 lines. If it's growing past that, the entry probably belongs in `notes.md`, not `CLAUDE.md`.
- Don't duplicate: if a line already exists, don't add it again.
- Don't contradict: if a new rule conflicts with an existing `CLAUDE.md` line, flag it to the user and ask which wins — don't silently add both.
- One block per file: never put `eval/` rules in `build/CLAUDE.md`, etc.

## 4. Confirm

Show the user a 3–5 line summary of what moved where before finishing, so the write is reviewable.
