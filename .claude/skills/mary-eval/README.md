# Mary Eval (skill)

Simulate operators talking to the Machine Mary Dify agent, and score how Mary
does — no coding, no scenario files required.

## One-time setup

1. **Install the skill.** Use the *Save skill* button when Claude shares the
   `.skill` file, or add it in **Settings → Capabilities**.
2. **Get your Dify app API key.** In the Dify app: **API Access → API Key**
   (format `app-...`). This is the app key, *not* the MCP server URL.
3. **Save the key once in a `.env`.** Copy `.env.example` to `.env` and paste
   your key into it. The scripts auto-load `.env` from your folder (or from
   `~/.mary-eval.env`), so you never have to re-enter it. Your `.env` is
   git-ignored and never written by Claude — you fill it in yourself.

## Using it — simulate (default)

Just describe a situation in chat, e.g.:
> Simulate an operator with a coolant pressure problem on haas_vf2 and see if Mary gets there.

Claude will first confirm the **operator ID** and **machine ID**, then play the
operator, have a real back-and-forth with Mary (revealing detail only as Mary
asks), and grade whether Mary converged on the true cause, stayed efficient,
and never fabricated alarms or numbers. You can ask for several simulations at
once.

> **Only registered machines work.** Mary loads real memory/past cases only for
> machine IDs registered in the system; a made-up ID won't behave correctly.
> `haas_vf2` is a known registered machine — a good default target.

## Using it — scripted suite (optional)

For a fixed, repeatable regression suite, copy `scenarios.example.yaml` to
`scenarios.yaml`, edit it in plain language, and say:
> Run the Mary eval suite on my scenarios.yaml

## What gets checked automatically

- No invented alarm numbers (Mary must defer on unknown codes).
- No invented feeds / speeds / tool lengths / offsets.
- Status never regresses after advancing.
- Lifecycle flags (`confirmed`, `closeout`) are honored.
- Every reply is valid `{capture, message, options, status}` JSON.
- Plus your per-scenario `expected_status`, `must_mention`, `must_not_mention`.

## Notes

- Multi-turn works because the runner carries Dify's `conversation_id` across
  turns — the MCP connector can't do that, which is why this talks to Dify's
  REST API directly.
- Your API key is used only at run time and never written to disk.
- Self-hosted Dify: set `DIFY_BASE_URL` (defaults to `https://api.dify.ai/v1`).
