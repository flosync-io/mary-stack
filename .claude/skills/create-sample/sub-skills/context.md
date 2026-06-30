# Sub-skill: context

Generates a `{name}_context.json` file for use in Alex evaluation fixtures.
The most complex sub-skill. Makes multiple focused LLM calls — one per section.
Called by the SKILL.md coordinator after scenario.md completes.

## Inputs received from coordinator

```
fm_id: string
persona_type: string
persona_yaml: object            — full output from persona.md
scenario_yaml: object           — full output from scenario.md
conversation_type: string       — single_action | multi_action
name_slug: string
```

## BEFORE STARTING — Check for escalation-only FM

Open `references/schema-guide.md`. If `fm_id` has `guardrail: true` OR the top cause's only procedure is an escalate-kind procedure with no steps:

→ **Skip to Step 8 (escalation-only path).** Do not generate observable_facts, checks, or steps.

Affected FMs: fm_safety_integrated_stop, fm_si_not_safely_referenced, fm_si_motion_monitoring_violation, fm_si_checksum_acceptance, fm_protection_zone_violation

---

## STANDARD PATH (operator-fix FMs)

### Step 1 — Traverse schema-guide.md (NO LLM)

From the FM block in schema-guide.md, extract:

```
top_cause      = cause with highest seed_prior → this is expected_cause
top_procedure  = top_cause.procedures[0] that is operator_fix kind → this is expected_procedure
checks[]       = top_cause.confirm_checks[] → the checks Alex must respond to
steps[]        = top_procedure.steps[] → the steps Alex must execute
safety_gates[] = top_procedure.safety_gate (the preliminary safety requirement)
```

Write these down. Every ID you use in the generated JSON must come from this list.

### Step 2 — Generate observable_facts (LLM call 1)

One observable_fact per check in `top_cause.confirm_checks[]`.

**EMBED THIS PROMPT VERBATIM:**

> "Generate observable_facts for a CNC machine troubleshooting context.
>
> Failure mode: [fm_id title from schema-guide]
> Operator persona: [persona_type] named [name]
> Their vocabulary — uses: [vocabulary_uses list]
> Their vocabulary — MUST NOT USE: [vocabulary_avoids list]
>
> For each of the following checks, generate one observable_fact object:
> [For each check: paste check_id, ask text, answers list, requires_guidance_for_naive flag]
>
> For each fact, generate:
> - fact_id: short snake_case label for what this fact captures (e.g. magazine_list_pocket, refractometer_reading)
> - actual_state: short enum-style string (e.g. tool_in_wrong_pocket, below_pds_band, level_present_and_reasonable)
> - what_operator_sees: what this operator physically sees or observes — in their vocabulary. NEVER a measurement or spec value unless the check explicitly produced a reading. NEVER a technical term from vocabulary_avoids. Must be 1–2 sentences describing physical observation only.
> - requires_guidance_to_find: [for naive_operator: use TRUE for all checks marked requires_guidance_for_naive:TRUE in the check list above. For experienced: false for all.]
> - guidance_response: if requires_guidance_to_find is true, what the operator says AFTER Mary explains where to find it. Null if false.
>
> Anti-patterns to avoid:
> - WRONG: 'The level is at 2.3 litres, below the minimum mark of 3.0 litres' (measurement the operator couldn't know)
> - RIGHT: 'The liquid in that window thing is way below the red line'
> - WRONG (naive): 'The refractometer reads 3 Brix, below the PDS band'
> - RIGHT (naive): 'I see a line on the little thing, it says about 3, is that right? That looks lower than the little chart on the side'
>
> NEVER use any of these terms in what_operator_sees or guidance_response: [vocabulary_avoids list]
>
> Respond only with a JSON array of observable_fact objects. No explanation, no preamble, no markdown fences."

### Step 3 — Generate check responses (LLM call 2)

One check response per check in `top_cause.confirm_checks[]`.

**EMBED THIS PROMPT VERBATIM:**

> "Generate check response objects for a CNC troubleshooting fixture.
>
> Persona: [persona_type] named [name], [experience_months] months experience
> Vocabulary uses: [list] | Vocabulary MUST NOT USE: [vocabulary_avoids list]
>
> For each check below, generate a check response object:
> [For each check: paste check_id, mary_will_likely_ask (from check.ask — near-verbatim), result_value (from check.answers — the confirming answer for this FM's top cause)]
>
> Fields to generate per check:
> - check_id: [copy verbatim — do not modify]
> - mary_will_likely_ask: copy the check.ask text with only light paraphrase — do not shorten or change meaning
> - alex_initial_response: how this operator first responds, before any guidance. Must be in their vocabulary. For naive: confusion if requires_guidance_to_find is true. For experienced: immediate answer in correct terms.
> - alex_after_guidance: if requires_guidance_to_find is true, what they say AFTER Mary explains where to look. Null if false.
> - result_value: [copy the confirming answer from check.answers — do not generate, copy verbatim]
>
> Examples:
> WRONG (naive, requires_guidance_to_find:true): alex_initial_response: 'I see the refractometer reads 3 Brix.'
> RIGHT (naive, requires_guidance_to_find:true): alex_initial_response: 'What's a refractometer? I don't know where that is.'
>
> WRONG (experienced): alex_initial_response: 'Uh I don't know where the Magazine list is'
> RIGHT (experienced): alex_initial_response: 'Already checked. T12 is in pocket 18 but the setup sheet says pocket 12.'
>
> NEVER use these terms in any operator response: [vocabulary_avoids list]
>
> Respond only with a JSON array of check objects. No explanation, no preamble, no markdown fences."

### Step 4 — Generate safety_gates (NO LLM — derived)

From the procedure's preliminary safety in schema-guide.md:

```json
[
  {
    "gate_id": "ppe_[short_label]",     // derive from the safety.require text
    "current_state": false,              // always false — gate not yet confirmed
    "alex_confirmation": "[operator confirms in their vocabulary — one sentence]"
  }
]
```

For naive operator: `alex_confirmation` must use plain language ("Okay I've got gloves on and my safety glasses, ready")
For experienced operator: can use slightly more technical phrasing ("Yep, spindle's stopped, changer's at rest")

Derive `gate_id` from the safety.ref field in schema-guide.md (e.g. `warn_coolant_ppe` → `gate_id: ppe_gloves_and_eye_protection`).

If the FM's procedure has no safety preliminary (null safety), then `safety_gates: []`.

### Step 5 — Generate step observations (LLM call 3 — multi_action ONLY)

Skip this step if `conversation_type: single_action`.

For single_action: generate a minimal steps array — just the final resolution step from the procedure, with `alex_can_do: true` and a brief `alex_observation`. Skip intermediate steps.

For multi_action, one step object per step in `top_procedure.steps[]`:

**EMBED THIS PROMPT VERBATIM:**

> "Generate step observation objects for a CNC troubleshooting fixture.
>
> Persona: [persona_type] named [name]
> Vocabulary uses: [list] | Vocabulary MUST NOT USE: [vocabulary_avoids list]
>
> For each step below, generate a step observation object:
> [For each step: paste step_id, action text, expected_result, on_deviation if present, skill]
>
> Fields per step:
> - step_id: [copy verbatim — do not modify]
> - action_description: 1-sentence plain-language summary of what this step involves (not the full action text)
> - alex_can_do: true (all these steps have skill: operator)
> - alex_observation: how this operator describes completing the step — in their vocabulary. Translate expected_result into what they would physically observe and report. 1–2 sentences.
> - expected_result: [copy from schema-guide verbatim — do not generate]
> - time_estimate_min: [copy from schema-guide cost.time_min — do not generate]
>
> NEVER use these terms in alex_observation: [vocabulary_avoids list]
>
> For naive: observations should be discovery-like ('Okay I zeroed it on the water like you said, now it reads zero')
> For experienced: observations should be crisp and confident ('Zeroed it. Zero on water. Ready.')
>
> Respond only with a JSON array of step objects. No explanation, no preamble, no markdown fences."

### Step 6 — Generate deviations (LLM call 4 — multi_action ONLY, or if on_deviation present in steps)

Skip if `conversation_type: single_action` AND no steps have `on_deviation` in schema-guide.md.

Source from `step.on_deviation` fields in schema-guide.md. Generate at least 1 deviation per multi_action fixture.

**EMBED THIS PROMPT VERBATIM:**

> "Generate deviation objects for a CNC troubleshooting fixture.
>
> Persona: [persona_type] named [name]
> Vocabulary uses: [list] | Vocabulary MUST NOT USE: [vocabulary_avoids list]
>
> For each on_deviation entry below, generate a deviation object:
> [For each: paste the step_id, on_deviation.policy, on_deviation.safe_state, on_deviation.branch_ref]
>
> Fields per deviation:
> - trigger: plain language description of what goes wrong at this step (what the operator observes)
> - alex_report: how this operator describes the deviation in their own voice — 1–2 sentences in their vocabulary
> - expected_mary_policy: [copy on_deviation.policy verbatim — do not generate]
> - expected_mary_response: what Mary should say — based on on_deviation.safe_state and policy. If policy is safe_state_escalate: Mary must stop, state safe state, escalate. If policy is reopen_diagnosis: Mary reopens diagnostic from the beginning. Do NOT invent procedures Mary hasn't been given.
>
> NEVER use these terms in alex_report: [vocabulary_avoids list]
>
> Respond only with a JSON array of deviation objects. No explanation, no preamble, no markdown fences."

### Step 7 — Generate patience_override (NO LLM — rule-based)

```
single_action: patience_override: null   (always — use persona defaults)

multi_action:
  patience_override:
    initial_patience: [persona.initial_patience + 2]   # longer conversations need more patience
    frustration_triggers: [copy from persona.patience.frustration_triggers — same list]
```

### Step 8 — Assemble context JSON

```json
{
  "context_id": "ctx_{fm_id_short}_{persona_type_short}_{name_slug}",
  "version": "2.0",
  "linked_scenario_id": "{scenario.scenario_id}",
  "linked_persona_id": "{persona.persona_id}",
  "target_failure_mode_id": "{fm_id}",
  "conversation_type": "{conversation_type}",
  "environment": {
    "shift": "{shift}",
    "time": "{scenario.time}",
    "machine_id": "ATI-VMC-03",
    "machine_model": "DMG MORI DMC 80",
    "machine_state": "{scenario.machine_state.alarm_active ? 'alarm_active' : 'running_no_alarm'}",
    "program_stopped": "{scenario.machine_state.program_stopped}",
    "senior_available": "{shift == 'night' ? false : true}",
    "recent_job": "{scenario.recent_job_description}",
    "alarm_displayed": "{scenario.alarm_code ? {code, text, hmi_color} : null}",
    "operator_knowledge": {
      "knows": "[list of 3–4 things this operator knows about the current situation, in their vocabulary]",
      "does_not_know": "[list of 2–3 things they don't know — these are the diagnostic gaps]",
      "vocabulary": {
        "uses": "{persona.vocabulary_uses}",
        "does_not_use": "{persona.vocabulary_avoids}"
      }
    }
  },
  "observable_facts": "[Step 2 output]",
  "procedure_tree": {
    "expected_cause": "{top_cause.cause_id}",
    "expected_procedure": "{top_procedure.procedure_id}",
    "checks": "[Step 3 output]",
    "safety_gates": "[Step 4 output]",
    "steps": "[Step 5 output]",
    "deviations": "[Step 6 output, or [] for single_action with no deviations]"
  },
  "expected_resolution": {
    "cause_confirmed": "{top_cause.cause_id}",
    "procedure_completed": "{top_procedure.procedure_id}",
    "outcome": "fixed",
    "total_time_estimate_min": "{sum of step time_estimate_min values}"
  },
  "patience_override": "{Step 7 output}"
}
```

---

## ESCALATION-ONLY PATH (Step 8 alternate)

For guardrail=true FMs and fm_protection_zone_violation:

```json
{
  "context_id": "ctx_{fm_id_short}_{persona_type_short}_{name_slug}",
  "version": "2.0",
  "linked_scenario_id": "{scenario.scenario_id}",
  "linked_persona_id": "{persona.persona_id}",
  "target_failure_mode_id": "{fm_id}",
  "conversation_type": "single_action",
  "environment": {
    "shift": "{shift}",
    "time": "{scenario.time}",
    "machine_id": "ATI-VMC-03",
    "machine_model": "DMG MORI DMC 80",
    "machine_state": "alarm_active",
    "program_stopped": true,
    "senior_available": "{shift == 'night' ? false : true}",
    "recent_job": "{scenario.recent_job_description}",
    "alarm_displayed": {
      "code": "{first alarm code from FM}",
      "text": "{paraphrase from FM observations}",
      "hmi_color": "red"
    },
    "operator_knowledge": {
      "knows": ["There is an alarm they haven't seen before", "The machine won't restart"],
      "does_not_know": ["What the alarm means", "Whether they can clear it themselves"],
      "vocabulary": {
        "uses": "{persona.vocabulary_uses}",
        "does_not_use": "{persona.vocabulary_avoids}"
      }
    }
  },
  "observable_facts": [
    {
      "fact_id": "alarm_number",
      "actual_state": "si_alarm_active",
      "what_operator_sees": "[what the operator sees on screen in their vocabulary]",
      "requires_guidance_to_find": false,
      "guidance_response": null
    }
  ],
  "procedure_tree": {
    "expected_cause": "{cause_id from FM}",
    "expected_procedure": "proc_escalate_safety",
    "checks": [
      {
        "check_id": "chk_alarm_number",
        "mary_will_likely_ask": "Read me the alarm NUMBER on the Diagnosis screen exactly (digits, including any leading band), not just the words.",
        "alex_initial_response": "[operator reads out the alarm number in their voice]",
        "alex_after_guidance": null,
        "result_value": "[the discriminating answer from chk_alarm_number for this FM's cause]"
      }
    ],
    "safety_gates": [],
    "steps": [],
    "deviations": []
  },
  "expected_resolution": {
    "cause_confirmed": "{cause_id}",
    "procedure_completed": "proc_escalate_safety",
    "outcome": "escalated",
    "total_time_estimate_min": 2
  },
  "patience_override": null
}
```

---

## CRITICAL VALIDATION — Before returning to coordinator

Run ALL of these checks. If any CRITICAL fails, do not return output — fix and regenerate.

**CRITICAL — blocks output:**
- [ ] `expected_cause` is in the FM's `causes[]` list in schema-guide.md
- [ ] `expected_procedure` is in schema-guide.md procedures list
- [ ] Every `check_id` in `procedure_tree.checks[]` is in the CRITICAL IDs list in schema-guide.md
- [ ] Every `step_id` in `procedure_tree.steps[]` is in the CRITICAL IDs list in schema-guide.md
- [ ] `observable_facts` is non-empty
- [ ] `procedure_tree.checks` is non-empty
- [ ] If `conversation_type: multi_action`: `steps[]` is non-empty AND `deviations[]` is non-empty
- [ ] If persona is naive_operator: no term from `vocabulary_avoids` appears in any free-text operator field
- [ ] If FM is guardrail=true or escalation-only: `steps: []` and `outcome: "escalated"`

**If a CRITICAL check fails:**
1. Identify which ID or field is incorrect
2. Look up the correct value in schema-guide.md
3. Fix and re-check before returning

## Reference

See `references/context-reference.json` for a complete, correct example (experienced_operator + fm_wrong_tool_data).
See `references/anti-patterns.md` for all 8 anti-patterns and what they catch.
See `references/schema-guide.md` CRITICAL IDs section for the complete list of valid IDs.
