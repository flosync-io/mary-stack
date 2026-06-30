# Sub-skill: persona

Generates a `{name}_persona.yaml` file for use in Alex evaluation fixtures.
Called by the SKILL.md coordinator after intake is complete. Never called directly by users.

## Inputs received from coordinator

```
fm_id: string                   — e.g. fm_wrong_tool_data
persona_type: string            — naive_operator | experienced_operator | leading_operator | adversarial_operator
name_slug: string               — e.g. wrong-tool-night
shift: string                   — day | night
```

## Step 1 — Load fixed fields

Open `references/persona-types.md` and copy ALL fixed fields for the given `persona_type` verbatim.
Do NOT generate: type, name, experience_months, skill_level, patience numeric values, quit_behavior.

## Step 2 — Load FM context

Open `references/schema-guide.md` and find the FM block for `fm_id`. Extract:
- `operator_phrases` → seed for `vocabulary_uses`
- `jargon_to_avoid_for_naive` → if persona_type is naive_operator, this IS `vocabulary_avoids`
- Check `ask` wording → seed specific frustration_trigger wording

## Step 3 — LLM generation

Generate only these fields (everything else is fixed):

### `vocabulary_uses`
- For naive_operator: everyday floor language only. Must include terms from `operator_phrases`. Must NOT include any term from `jargon_to_avoid_for_naive`. Examples: "the screen", "that panel", "it stopped", "alarm on screen", "red light"
- For experienced_operator: correct technical floor jargon. Must include alarm codes and component names relevant to this FM.
- For leading/adversarial: mix of floor language and some correct terms.

### `vocabulary_avoids`
- For naive_operator: copy `jargon_to_avoid_for_naive` from schema-guide.md for this FM exactly. Add any other technical terms that appear in the FM's check `ask` wording.
- For experienced_operator: only "SINUMERIK parameter numbers (will ask Mary to translate to plain terms if used)"
- For leading/adversarial: deep programming terms; parameter numbers

### `behavior_traits`
4–6 bullet points. Must be CONCRETE behaviors, not personality adjectives.

For naive_operator, must include at least:
- "asks where things are on the machine before they can check them"
- "describes components by appearance, not name ('that little window thing', 'the monocular looking thing')"
- "does not know what alarm codes mean"
- [1–2 FM-specific traits based on what checks they'll need to do]

For experienced_operator, must include at least:
- "states the alarm code and machine ID immediately without being asked"
- "already tried one or two things before calling for help, and says so upfront"
- "dislikes being walked through steps they already know"
- [1–2 FM-specific traits]

### `patience.frustration_triggers`
2–4 triggers. MUST be specific and objectively checkable. Include FM-specific terminology.

**INCLUDE VERBATIM in your LLM call:**
> "Write 2–4 frustration triggers that fire on objectively observable events in Mary's response — not vague tone judgments. Use this formula: [Mary does specific observable thing] when [operator already provided that information / doesn't know that term / already told her X]. WRONG: 'Mary uses jargon'. RIGHT: 'Mary uses the term "Magazine list" without explaining that it's the tool-position screen on the control panel.' WRONG: 'Mary is unhelpful.' RIGHT: 'Mary asks about the alarm number after the operator already quoted it in the opening message.'"

### `description`
One paragraph, 3–5 sentences. Written for the Alex agent system prompt. Describes who this operator is, what they know, how they communicate, and what makes them distinctive for this FM.

## Step 4 — Assemble YAML

```yaml
persona_id: {persona_type}_{fm_id_short}_{name_slug}   # e.g. naive_operator_wtd_tool-night
type: {persona_type}
name: {name from persona-types.md}
experience_months: {fixed value}
shift: {shift}
languages:
  - en

vocabulary_uses:
  {LLM-generated list}

vocabulary_avoids:
  {LLM-generated list — verbatim jargon list for naive}

behavior_traits:
  {LLM-generated list}

patience:
  initial_patience: {fixed}
  decay_per_turn: {fixed}
  frustration_triggers:
    {LLM-generated list}
  quit_threshold: {fixed}
  quit_behavior: {fixed}

skill_level: {fixed}

description: >
  {LLM-generated paragraph}
```

## Step 5 — Validation checks (before returning to coordinator)

Before passing output to coordinator:
- [ ] All fixed fields match persona-types.md exactly (no modified patience values)
- [ ] `vocabulary_avoids` for naive_operator contains all terms from schema-guide.md `jargon_to_avoid_for_naive`
- [ ] No term from `vocabulary_avoids` appears in any `behavior_traits` or `description` text attributed to the operator
- [ ] `frustration_triggers` are FM-specific (contain at least one concrete term or action from this FM's check wording)
- [ ] `frustration_triggers` do NOT include generic phrases like "Mary is unhelpful", "Mary takes too long", "Mary uses jargon"

## Reference

See `references/persona-reference.yaml` for a complete, correct example (experienced_operator + fm_wrong_tool_data).
See `references/persona-types.md` for all fixed field values.
See `references/anti-patterns.md` §AP-4 for frustration trigger guidance.
