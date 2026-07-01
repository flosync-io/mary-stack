# voice-agents — ElevenLabs Conversational AI configs

Local mirror of agents on the ElevenLabs platform (pulled with `elevenlabs agents pull --all`). Interview/shift-handover bots that feed raw source material upstream of `distill/` — not part of the `knowledge.json` contract itself.

## Push guardrail — READ BEFORE RUNNING `elevenlabs agents push`

`elevenlabs agents push` mutates **live production agents** on the ElevenLabs platform — it is not a local, reversible action. Real callers/operators may be talking to these agents.

**Never run `elevenlabs agents push` (or `tools push` / `tests push`) unless the user's message contains the literal phrase "yes push to prod".**

- A generic "push it", "deploy this", "sync it up", "looks good" — does NOT count. Ask for the literal phrase instead of inferring consent.
- `--dry-run` is exempt from this rule — always safe to run and preferred before any real push, to show the user the diff first.
- Editing local files in `agent_configs/` is fine without confirmation; only the push itself is gated.
- This applies to edits made by Claude in this session AND to pushing changes a human made to these files — if asked to push someone else's edits, the same phrase is still required.

## Layout

- `agents.json` — registry mapping agent name → config file → agent_id/version_id/branch_id
- `agent_configs/*.json` — one file per agent, full `conversation_config` + `platform_settings`
- Pull latest before editing: `elevenlabs agents pull --all` (or `--agent <id>` for one)
