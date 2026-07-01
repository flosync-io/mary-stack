# voice-agents

Local mirror of the "Phil" ElevenLabs Conversational AI agents used for shift-related voice interviews on the shop floor. Managed with the [`elevenlabs` CLI](https://www.npmjs.com/package/@elevenlabs/cli).

## Agents

| Agent | File | Purpose |
|---|---|---|
| `phil_shift_handover` | `agent_configs/phil_shift_handover.json` | Debriefs a shift leader at end-of-shift, capturing incidents/resolutions/open items for the next shift. Feeds source material upstream of `distill/`. |
| `phil_the_interviewer` | `agent_configs/phil_the_interviewer.json` | General interviewer persona. |

## Setup

```bash
npm install -g @elevenlabs/cli
elevenlabs auth login   # uses ELEVENLABS_API_KEY, see .env.example
```

## Common commands

```bash
# Pull latest config for these two agents from the platform
elevenlabs agents pull --agent <agent_id> --all

# Preview local changes against the live platform (always safe)
elevenlabs agents push --dry-run

# Push local changes live — see CLAUDE.md, requires explicit confirmation
elevenlabs agents push
```

## Before you push

Read `CLAUDE.md` in this directory — pushing mutates live production agents and requires the user to explicitly say "yes push to prod".
