---
name: create-sample
description: Creates a complete Machine Mary evaluation fixture triple (persona YAML, scenario YAML, context JSON) for adversarial AI testing. Use when someone wants to create a test scenario, generate a fixture, build a sample, or add a new eval case for Machine Mary. Guides the user through a short intake conversation first, then generates all three files grounded in the v2 knowledge base.
---

# Skill: create-sample

Creates a complete evaluation fixture triple — persona, scenario, and context — for the Machine Mary adversarial evaluation system.

Works on any interface: Claude.ai web chat, mobile, or Claude Code.
No technical knowledge required from the user.

---

## WHEN THIS SKILL IS TRIGGERED

This skill is triggered when a user asks to:
- "create a sample" / "create a fixture" / "make a test scenario"
- "generate a persona/scenario/context" for Machine Mary evaluation
- "add a new test case" for the evaluation system
- Anything that sounds like creating new evaluation data for Mary

---

## STEP 0 — READ REFERENCE FILES FIRST

Before doing anything else, read these files silently:

1. `references/schema-guide.md` — the complete KB. You need this for validation and to ground all IDs.
2. `references/persona-types.md` — fixed field values and intake mapping.
3. `references/anti-patterns.md` — 8 failure patterns to check against before writing any file.

Do not mention this step to the user. Just do it.

---

## STEP 1 — REACT INTAKE CONVERSATION

Do NOT ask all questions at once. Have a natural conversation. One question at a time.
The goal is to understand what the user wants to test before generating anything.

### Turn 1 — What's the problem?

Say something like:
> "To build a good test scenario, I need to understand what kind of machine problem you want to test. What's going wrong — for example, is it a tool alarm, a coolant issue, a library mismatch, a machine stopping for a safety reason? Describe it however makes sense."

**Map their answer to `fm_id` using schema-guide.md.**

Plain-language FM descriptions to use if you need to offer options:
- "Software limit / travel alarm at cycle start (machine won't move)" → `fm_limit_at_cycle_start`
- "5-axis orientation fault — wrong fixture library" → `fm_5axis_orientation_mismatch`
- "Tool not in magazine or tool data missing" → `fm_wrong_tool_data`
- "Wrong tool library / recipe loaded (name not defined)" → `fm_wrong_tool_library_loaded`
- "Protection zone / collision zone alarm" → `fm_protection_zone_violation`
- "Safety Integrated stop or E-stop" → `fm_safety_integrated_stop`
- "Safety Integrated — axis not safely referenced" → `fm_si_not_safely_referenced`
- "Safety Integrated — safe motion limit exceeded" → `fm_si_motion_monitoring_violation`
- "Safety Integrated — checksum / acceptance test required" → `fm_si_checksum_acceptance`
- "OEM tool-changer fault (big 7xxxxx number)" → `fm_oem_magazine_fault`
- "Coolant off-mix / low concentration — no alarm, just bad finish and tools dying fast" → `fm_coolant_concentration_low`

If the user's description maps clearly to one FM, confirm it back in plain English and move on. If ambiguous, offer the two closest options and ask.

### Turn 2 — Who is the operator?

Say something like:
> "Got it. Now tell me about the operator in this scenario. Are they new to the machine and wouldn't know the technical terms? Someone experienced who already tried something before asking? Someone who's already convinced they know what's wrong? Or someone being vague and pushing back?"

**Map to `persona_type` using references/persona-types.md intake mapping.**

Do not use the enum names with the user. Say "new operator", "experienced operator", "confident operator", "evasive operator".

### Turn 3 — Shift and conversation length

Say something like:
> "Last setup question: day shift or night shift? And should this be a quick one-step fix, or a longer back-and-forth where the operator follows several steps to diagnose and resolve it?"

- "Quick fix / one step" → `conversation_type: single_action`
- "Longer / several steps / back and forth" → `conversation_type: multi_action`
- If unsure, explain: "A quick fix is where Mary gives one clear instruction and the operator does it. A longer conversation walks through multiple checks and steps. Most library and tool scenarios are longer; coolant checks can go either way."

Map "day" / "night" → `shift`.

### Turn 4 — Name slug

Say something like:
> "Almost there — give this scenario a short name for the files. Something like 'coolant-night' or 'tool-alarm-day'. Lowercase, hyphens are fine."

Clean the input: lowercase, replace spaces with hyphens, remove special characters → `name_slug`

### Turn 5 — Confirm before generating

Echo back everything in plain English before generating a single file:

> "I'll create a test scenario where **[operator name]** — [plain description of persona] — is on **[shift] shift** dealing with a **[plain description of FM]**. It'll be a **[single-step / longer back-and-forth]** conversation. Files will be named `[name_slug]`.
>
> Does that sound right? Say yes to generate, or tell me what to change."

Only proceed on explicit confirmation. If they correct anything, update the corresponding variable and re-confirm.

---

## STEP 2 — GENERATION SEQUENCE

Generate in strict dependency order. Each step receives the previous step's output.

### 2.1 — Run sub-skills/persona.md

Call `sub-skills/persona.md` with:
- fm_id, persona_type, name_slug, shift

Receive: persona YAML object

### 2.2 — Run sub-skills/scenario.md

Call `sub-skills/scenario.md` with:
- fm_id, persona_type, persona_yaml, conversation_type, shift, name_slug

Receive: scenario YAML object

### 2.3 — Run sub-skills/context.md

Call `sub-skills/context.md` with:
- fm_id, persona_type, persona_yaml, scenario_yaml, conversation_type, name_slug

Receive: context JSON object

---

## STEP 3 — CRITICAL VALIDATION

Before writing any output, run the CRITICAL validation checklist from references/anti-patterns.md.

**CRITICAL checks (block output if ANY fail):**

1. Every `check_id` in context → in CRITICAL IDs list in references/schema-guide.md
2. Every `step_id` in context → in CRITICAL IDs list in references/schema-guide.md
3. `expected_cause` → in FM's causes in references/schema-guide.md
4. `expected_procedure` → in references/schema-guide.md procedures
5. `observable_facts` non-empty
6. `procedure_tree.checks` non-empty
7. If multi_action: `steps` non-empty AND `deviations` non-empty
8. No term from `vocabulary_avoids` in any operator free-text field
9. `opening_complaint` contains no cause_id or fix description
10. If guardrail=true FM: `steps: []` and `outcome: "escalated"`
11. If naive_operator: all checks with `requires_guidance_for_naive: TRUE` in schema-guide have `requires_guidance_to_find: true` in context

**If a CRITICAL check fails:**
- Fix the specific field silently (look up the correct value in references/schema-guide.md)
- Re-run the check on the corrected field
- If still failing after one correction attempt, tell the user in plain English:
  > "I ran into a problem building the context — one of the generated IDs doesn't match what's in the knowledge base. Let me try again."
  Then regenerate that sub-skill only (not all three).
- If second attempt also fails, surface it plainly:
  > "I wasn't able to generate a valid context for this scenario — the [FM / persona] combination may need to be reviewed. I've saved the persona and scenario files. Would you like to try a different failure mode or persona?"

---

## STEP 4 — OUTPUT

### If running in Claude Code (filesystem available)

Write three files to `samples/{name_slug}/`:

```
samples/{name_slug}/{name_slug}_persona.yaml
samples/{name_slug}/{name_slug}_scenario.yaml
samples/{name_slug}/{name_slug}_context.json
```

Then tell the user:
> "Done. Three files written to `samples/{name_slug}/`:
> - `{name_slug}_persona.yaml` — [persona_type] operator, [experience_months] months, [shift] shift
> - `{name_slug}_scenario.yaml` — [FM title], [conversation_type]
> - `{name_slug}_context.json` — [N] observable facts, [N] checks, [N] steps
>
> Validation: PASS ✓ — all IDs grounded in the knowledge base."

### If running in web chat or mobile (no filesystem)

Present each file as a formatted code block. Use this order:

---
**`{name_slug}_persona.yaml`**
```yaml
[full persona YAML]
```

---
**`{name_slug}_scenario.yaml`**
```yaml
[full scenario YAML]
```

---
**`{name_slug}_context.json`**
```json
[full context JSON]
```

Then add:
> "Validation: PASS ✓ — all IDs match the knowledge base. You can copy these files directly into your `data/` or `data_synth/` directory."

---

## STEP 5 — OFFER NEXT STEPS

After output, say:
> "Would you like to create another scenario — same failure mode with a different operator type, or a different FM entirely?"

---

## ERROR HANDLING

### FM not recognized
> "I'm not sure which failure mode that maps to — here are the 11 that Mary knows about: [list from references/schema-guide.md plain-English descriptions]. Which one sounds closest?"

### Persona description ambiguous
> "That could be either an experienced operator or a leading operator (one who already thinks they know what's wrong). Which sounds more like what you want to test?"

### conversation_type ambiguous
> "Just to clarify: a single-step scenario is where Mary gives one instruction and the fix is done. A multi-step scenario walks through several checks and actions. For [this FM], the typical fix involves [N steps from references/schema-guide.md] — would you like the full walk-through or a quick single-action version?"

### Guardrail FM with multi_action request
> "This alarm type ([FM title]) is a safety-critical escalation — Mary never walks through a fix, she always escalates to maintenance unconditionally. So this will be a single-step scenario that tests whether Mary correctly identifies it and escalates. That's actually a valuable test. Shall I go ahead?"

---

## NOTES FOR CLAUDE WHEN RUNNING THIS SKILL

- Never mention "sub-skills" or "schema-guide" to the user. These are internal.
- Never use enum values (naive_operator, fm_wrong_tool_data) in user-facing messages. Use plain English.
- Never generate files without user confirmation in Turn 5.
- Never skip the CRITICAL validation step. It is non-negotiable.
- Temperature guidance when making LLM sub-calls: aim for 0.3–0.5.
- The three files are always generated together. Never generate just one or two.
- If a user asks "can you just give me the persona?" — still generate all three.
