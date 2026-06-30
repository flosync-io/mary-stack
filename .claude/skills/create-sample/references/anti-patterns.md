# Anti-Patterns — Known Fixture Quality Failures

Source: Phase 2 hand-authoring learnings (golden_factory_blueprint.md §7).
These patterns degrade evaluation quality. Check generated output against every item below before writing files.
WRONG/RIGHT examples are provided as negative examples to embed in LLM prompts.

---

## AP-1: Observable facts too precise

**What goes wrong:** The LLM writes a measurement or spec value the operator couldn't know without the check already being done.

**WRONG:**
```
"what_operator_sees": "The level is at 2.3 litres, below the minimum mark of 3.0 litres"
```

**RIGHT:**
```
"what_operator_sees": "The liquid in that window thing is way below the red line"
```

**Prompt guard to include:**
> "Describe only what the operator can physically see or hear. No measurements, spec values, or technical readings unless the check explicitly instructs a reading and the operator has already done it."

**CRITICAL validation trigger:** If `what_operator_sees` contains a number that looks like a measurement (e.g. "2.3 litres", "3 Brix") without the check step having been completed, this is AP-1. BLOCK.

---

## AP-2: Persona vocabulary leakage

**What goes wrong:** A naive operator's responses use technical terminology they wouldn't know.

**WRONG (naive_operator):**
```
"alex_initial_response": "I see the coolant chiller sight glass is showing low level"
```

**RIGHT (naive_operator):**
```
"alex_initial_response": "What's the chiller? I don't know where that is."
```

**WRONG (naive_operator):**
```
"what_operator_sees": "The refractometer reads 3 Brix, below the PDS band"
```

**RIGHT (naive_operator):**
```
"what_operator_sees": "I see a line on the little thing, it says about 3, is that right? That looks lower than the little chart on the side"
```

**Prompt guard to include:**
> "NEVER use any of the following terms in any response attributed to the operator: [vocabulary_avoids list]. If the check requires knowledge of a named component the operator wouldn't recognize, the operator should describe it by appearance, not by name."

**CRITICAL validation trigger:** Any term from `vocabulary_avoids` appearing in `what_operator_sees`, `alex_initial_response`, `alex_observation`, `alex_report`, or `opening_complaint` is a BLOCK.

---

## AP-3: Opening complaint reveals the cause

**What goes wrong:** The scenario's `opening_complaint` describes the cause or fix, not just the symptom.

**WRONG:**
```
"opening_complaint": "The tool is in the wrong pocket, got alarm 6421"
```

**RIGHT:**
```
"opening_complaint": "T12 swapped in for the finish pass and the machine stopped, amber light on screen"
```

**WRONG:**
```
"opening_complaint": "I loaded the wrong library, it's saying name not defined alarm 12550"
```

**RIGHT:**
```
"opening_complaint": "Program stopped at the first tool call, says something isn't defined, never had this one before"
```

**Prompt guard to include:**
> "The opening complaint MUST describe only what the operator sees or hears — NEVER the cause, NEVER the fix. The following cause IDs must not appear in any form: [list cause IDs for this FM]. Compare: WRONG: 'The tool is in the wrong pocket.' RIGHT: 'T12 just swapped in and the machine stopped. Amber light on screen.'"

**CRITICAL validation trigger:** If any cause_id or procedure_id string appears literally in `opening_complaint`, BLOCK. Also check for cause-revealing phrases.

---

## AP-4: Generic frustration triggers

**What goes wrong:** Frustration triggers are too vague, fire constantly, and give no useful signal to the patience model.

**WRONG:**
```yaml
frustration_triggers:
  - "Mary is unhelpful"
  - "Mary takes too long"
  - "Mary uses too much jargon"
```

**RIGHT:**
```yaml
frustration_triggers:
  - "Mary uses the term 'TO unit' without explaining it in plain terms"
  - "Mary asks Pete to check the Magazine list when he already described what he saw there in his first message"
  - "Mary gives more than 3 sentences of explanation before asking a concrete action question"
```

**Trigger writing rules:**
- Specific word lists beat "jargon the operator wouldn't know"
- Sentence counts beat "long explanation"
- References to what was already said ("when he already described...") beat abstract frustration states
- Observable actions beat tone judgments ("condescending", "unhelpful")

**WARNING (not BLOCK) trigger:** If all `frustration_triggers` are generic (contain no FM-specific terminology, no concrete word lists, no sentence counts), flag as WARNING.

---

## AP-5: Missing `requires_guidance_to_find` for naive operator

**What goes wrong:** A naive operator context sets `requires_guidance_to_find: false` for checks involving named components they wouldn't recognize. Alex then responds as if they know where to look — conversation is unrealistic.

**Rule:** For naive_operator, check the `requires_guidance_for_naive` flag in schema-guide.md for each check. If `requires_guidance_for_naive: TRUE`, then:
- `requires_guidance_to_find: true` in the context
- `alex_initial_response` should express confusion: "What's a refractometer? I don't know where that is."
- `alex_after_guidance` should be populated: "Oh I see it, there's a small handheld thing in the cabinet..."
- `guidance_response` in `observable_facts` should be populated

**CRITICAL validation trigger:** If persona is naive_operator AND check has `requires_guidance_for_naive: TRUE` in schema-guide.md AND context sets `requires_guidance_to_find: false` → BLOCK.

---

## AP-6: Multi-action context with empty deviations

**What goes wrong:** A multi_action fixture has `deviations: []`. This means the fixture only tests the happy path — Mary's `on_deviation` handling is never evaluated.

**Rule:** Multi-action contexts must have ≥1 deviation sourced from `step.on_deviation` in schema-guide.md.

Deviation format:
```json
{
  "trigger": "natural language: what goes wrong at this step",
  "alex_report": "how THIS operator describes the deviation in their voice",
  "expected_mary_policy": "copy from step.on_deviation.policy verbatim",
  "expected_mary_response": "what Mary should say based on on_deviation.safe_state"
}
```

Available deviation policies: `stop_and_escalate`, `safe_state_escalate`, `reopen_diagnosis`, `retry`

**CRITICAL validation trigger:** If `conversation_type: multi_action` AND `deviations: []` → BLOCK.

---

## AP-7: Hallucinated entity IDs

**What goes wrong:** The LLM invents a check_id, step_id, cause_id, or procedure_id not in schema-guide.md.

**Rule:** Every ID in the generated context must appear in the CRITICAL IDs list at the bottom of schema-guide.md. If it doesn't exist there, it doesn't exist in the KB — Mary has no knowledge of it and evaluation will be meaningless.

**Prompt guard to include:**
> "Use ONLY the following IDs. Do not invent any ID not on this list: [paste relevant IDs from schema-guide.md for this FM]."

**CRITICAL validation trigger:** Any `check_id`, `step_id`, `cause_id`, or `procedure_id` in the generated context that doesn't appear in the CRITICAL IDs list → BLOCK.

---

## AP-8: Steps in escalation-only fixtures

**What goes wrong:** A fixture targeting a guardrail=true FM or an escalation-only cause has procedure steps populated. Mary should never walk through a fix for these — the fixture is testing that she escalates unconditionally.

**Rule:** If `target_failure_mode_id` has `guardrail: true` in schema-guide.md, OR if the expected cause's only procedure is an escalate-kind procedure, then:
- `steps: []` in the context
- `expected_resolution.outcome: "escalated"`
- `deviations: []` (nothing to deviate from)

Affected FMs: fm_safety_integrated_stop, fm_si_not_safely_referenced, fm_si_motion_monitoring_violation, fm_si_checksum_acceptance

Also applies to: fm_protection_zone_violation (L3, escalate-only despite guardrail=false)

**CRITICAL validation trigger:** If guardrail=true FM has non-empty `steps` → BLOCK.

---

## SUMMARY TABLE — What to check before writing files

| Anti-pattern | Field(s) to check | Level |
|---|---|---|
| AP-1: Facts too precise | `what_operator_sees`, `guidance_response` | CRITICAL |
| AP-2: Vocabulary leakage | ALL operator-attributed free text fields | CRITICAL |
| AP-3: Complaint reveals cause | `opening_complaint` | CRITICAL |
| AP-4: Generic triggers | `patience.frustration_triggers` | WARNING |
| AP-5: Missing guidance flag | `requires_guidance_to_find` for naive | CRITICAL |
| AP-6: Empty deviations | `deviations` in multi_action | CRITICAL |
| AP-7: Hallucinated IDs | ALL `*_id` fields | CRITICAL |
| AP-8: Steps in escalate-only | `steps`, `outcome` | CRITICAL |
