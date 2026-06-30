# Sub-skill: scenario

Generates a `{name}_scenario.yaml` file for use in Alex evaluation fixtures.
Called by the SKILL.md coordinator after persona.md completes. Receives persona output as input.

## Inputs received from coordinator

```
fm_id: string                   — e.g. fm_wrong_tool_data
persona_type: string            — naive_operator | experienced_operator | leading_operator | adversarial_operator
persona_yaml: object            — the full output from persona.md
conversation_type: string       — single_action | multi_action
shift: string                   — day | night
name_slug: string               — e.g. wrong-tool-night
```

## Step 1 — Pull FM data from schema-guide.md (NO LLM — copy verbatim)

Open `references/schema-guide.md` and find the FM block for `fm_id`. Extract these fields directly — do NOT generate them:

```
alarm_codes[]          → machine_state.alarm_code (use first code in list)
alarm_codes[]          → machine_state.alarm_code_display (join all with ", ")
guardrail              → determines whether machine stops or keeps running
typical_context        → seed for shift/operation context
operator_phrases[]     → seed for opening_complaint voice
```

Set these fields from schema-guide data (no LLM):
- `machine_state.alarm_active`: true if FM has alarm_codes (false for fm_coolant_concentration_low)
- `machine_state.program_stopped`: true if FM guardrail=true OR if fm is a stop-class FM; false for fm_coolant_concentration_low
- `machine_state.machine_running`: true only for fm_coolant_concentration_low
- `machine_state.alarm_code`: first alarm code from FM's alarm_codes[] (null if empty)
- `machine_state.alarm_text`: derive from FM's observations[0] — paraphrase in 4–8 words, do NOT quote verbatim
- `machine_state.hmi_color`: "amber" for most alarms, "red" for guardrail=true FMs, null for fm_coolant_concentration_low

## Step 2 — Derive time and machine context

Set without LLM:
- `shift`: from coordinator input
- `time`: day shift → "09:00"–"15:00" range; night shift → "01:00"–"04:00" range (pick a specific time)
- `machine_id`: "ATI-VMC-03" (use this; do not invent)
- `machine_model`: "DMG MORI DMC 80" (fixed; do not change)

## Step 3 — LLM generation

Generate ONLY these fields. Include the prompt guards verbatim in your LLM call.

### `opening_complaint`
The most critical field. This is what Alex says at the very start of the conversation.

**EMBED THIS GUARD VERBATIM IN YOUR LLM CALL:**

> "Write the opening complaint the operator says to Mary at the start of a support conversation. Rules:
> 1. Describe ONLY what the operator sees or hears — NEVER the cause, NEVER the fix.
> 2. Write in the operator's vocabulary: use terms from vocabulary_uses: [list], avoid ALL terms from vocabulary_avoids: [list].
> 3. Match the shift context: it's [shift] shift, [time], machine [machine_id].
> 4. The following cause IDs MUST NOT appear in any form (not as words, not paraphrased): [list cause IDs for this FM].
> 5. WRONG: 'The tool is in the wrong pocket, got alarm 6421.' RIGHT: 'T12 swapped in for the finish pass and the machine stopped. Amber light on screen.'
> 6. WRONG: 'I loaded the wrong library.' RIGHT: 'Program stopped at the first tool call, says something isn't defined.'
> 7. WRONG (coolant): 'The coolant concentration is low.' RIGHT: 'The finish started going off about an hour ago and we're burning through tools.'
> Respond with only the opening_complaint string, no explanation."

### `recent_job_description`
One sentence describing a plausible job that would lead to this FM. Must be consistent with titanium aerospace part machining on a DMG MORI DMC 80. Match the FM's `typical_context`. Example: "OP30 finish pass on a titanium bracket, T12 swapped in at the start of the pass"

### `title`
4–8 words. Describes the scenario factually. Does NOT reveal the cause.
Example: "Wrong tool alarm on night shift" not "Tool in wrong pocket — naive operator"

### `description`
2–3 sentence narrative paragraph. Written for the Alex agent system prompt. Sets the scene: who this operator is, what shift, what they were doing when it happened, what they see. Written in third person. Uses vocabulary appropriate to persona. Does not reveal the cause.

## Step 4 — Assemble YAML

```yaml
scenario_id: scen_{fm_id_short}_{shift}_{name_slug}   # e.g. scen_wtd_night_tool-night
title: {LLM-generated}
target_failure_mode_id: {fm_id}
conversation_type: {conversation_type}

machine_state:
  machine_id: ATI-VMC-03
  machine_model: DMG MORI DMC 80
  alarm_active: {derived from FM data}
  alarm_code: {from schema-guide, null if empty}
  alarm_text: {paraphrased from FM observations, null if empty}
  hmi_color: {amber|red|null}
  program_stopped: {derived}
  machine_running: {derived}

shift: {shift}
time: {picked time string}

opening_complaint: >
  {LLM-generated — passes all guards}

recent_job_description: >
  {LLM-generated}

description: >
  {LLM-generated}
```

## Step 5 — Validation checks (before returning to coordinator)

Before passing output to coordinator:
- [ ] `alarm_code` matches a code in schema-guide.md for this FM (not invented)
- [ ] `opening_complaint` contains NO term from `vocabulary_avoids`
- [ ] `opening_complaint` contains NO cause_id or procedure_id string
- [ ] `opening_complaint` does NOT describe the cause (tool in wrong pocket, library mismatch, etc.)
- [ ] `opening_complaint` describes symptoms only (what the operator sees/hears/feels)
- [ ] `machine_state` fields are consistent with each other (running machine has no alarm_code for fm_coolant_concentration_low)
- [ ] For guardrail=true FMs: `hmi_color` is "red", `program_stopped` is true

## Escalation-only FM notes

For FMs 5–9 (protection zone, all SI variants):
- `alarm_active`: true
- `program_stopped`: true
- `machine_running`: false
- `opening_complaint` must sound alarming but NOT reveal the cause ("there's an alarm I haven't seen before, big numbers, machine won't restart")
- `hmi_color`: "red" for guardrail=true FMs

For fm_coolant_concentration_low:
- `alarm_active`: false, `alarm_code`: null, `alarm_text`: null
- `program_stopped`: false, `machine_running`: true
- Opening complaint describes quality symptoms only (finish, tool life, smell)

## Reference

See `references/scenario-reference.yaml` for a complete, correct example (experienced_operator + fm_wrong_tool_data).
See `references/anti-patterns.md` §AP-3 for opening complaint guard.
