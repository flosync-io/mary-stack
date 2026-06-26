#!/usr/bin/env python3
"""
distill/draft_add.py — LLM-assisted draft for ADD failure_modes.

draft_add(runtime, knowledge) -> dict
  Pure function: no Supabase, no file I/O. Takes a resolved runtime blob
  (status=resolved, matched_fm=null — the ADD path in promote.py) and returns
  a schema-shaped failure_mode draft.

  Non-negotiable rules baked into the prompt:
    1. operator_phrases seeded verbatim from the operator's own words.
    2. component_ref / title / guardrail emitted as TODO sentinel strings
       (not grounded in the runtime → human must author on review).

CLI wrapper:
  Reads a runtime blob (via storage or a local JSON file), calls draft_add,
  writes out/add_<conv>.draft.json. On LLM parse failure, writes
  out/add_<conv>.draft.RAW.txt and exits 1.

Requires OPENAI_API_KEY in environment or repo-root .env.
"""
import json, os, re, sys
from pathlib import Path


TODO = "TODO: human must author — do not fabricate"


def _load_env(path=None):
    candidates = [Path(path)] if path else []
    candidates += [
        Path(__file__).parent.parent / ".env",
        Path.home() / ".mary.env",
    ]
    for p in candidates:
        if p.exists():
            with open(p) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, _, v = line.partition("=")
                        os.environ.setdefault(k.strip(), v.strip())
            return


def _fm_id(symptom, existing_ids=None):
    words = re.findall(r"[a-z0-9]+", (symptom or "unknown").lower())
    base = "fm_" + "_".join(words[:4])
    if not existing_ids:
        return base
    cand, i = base, 2
    while cand in existing_ids:
        cand = f"{base}_{i}"; i += 1
    return cand


_PROMPT_TEMPLATE = """\
You are a machine-knowledge author for a CNC shop floor. An operator fixed a \
fault that the diagnostic engine did not recognise. Produce a draft failure_mode \
object so it can be added to the knowledge base.

INPUTS
------
reported (operator's symptom):      {reported}
resolution_note (operator's fix):   {resolution}
sanity_notes:                       {sanity}
checks performed (from session):    {checks}
confirmed_cause id (if any):        {confirmed_cause}

TARGET SCHEMA (produce JSON that matches this shape exactly)
------------------------------------------------------------
{{
  "id":            "string — snake_case, fm_ prefix, derived from symptom",
  "component_ref": "string — component id (see rule 2)",
  "title":         "string — short human title (see rule 2)",
  "guardrail":     "boolean — true = escalate-always (see rule 2)",
  "case_count":    1,
  "symptom_signature": {{
    "conditions":       "array of [component_ref_placeholder, state_string] pairs",
    "observations":     "array of observation strings derived from reported/sanity",
    "alarm_codes":      "array of alarm code strings (see rule 4)",
    "operator_phrases": "array — VERBATIM operator words (see rule 1)"
  }},
  "causes": [{{
    "id":             "string — snake_case, cause_ prefix",
    "mechanism":      "string — what physically failed (from resolution_note)",
    "seed_prior":     0,
    "case_count":     1,
    "action_level":   "L2",
    "escalate_to":    "maintenance",
    "confirm_checks": [],
    "procedures":     []
  }}],
  "aliases":      "array of short label strings for MatchScore",
  "anti_pattern": "string — common wrong diagnosis if obvious, else empty string"
}}

RULES — violations will be rejected by the human reviewer
---------------------------------------------------------
1. operator_phrases MUST be seeded verbatim from the operator's actual words in
   'reported' and 'resolution_note'. Copy their phrasing literally —
   "clamp's not holding", "part keeps creeping", "no alarm" — do NOT rephrase
   into manual-speak. These are what make the FM reachable by the next operator
   who describes the fault in the same words.

2. Do NOT fabricate component_ref, title, or guardrail. Emit each as the exact
   string: "TODO: human must author — do not fabricate"
   (guardrail is boolean in the schema but use this string in the draft —
   the human will replace it during review.)

3. For causes: one stub only. Derive mechanism from resolution_note text.
   Leave confirm_checks and procedures as empty arrays — no checks/procedures
   exist yet. Use action_level="L2" and escalate_to="maintenance" as safe
   defaults; add a "$todo_review" field on the cause if these feel wrong.

4. alarm_codes: use [] if no alarm code appears in the inputs. NEVER invent
   alarm numbers. The builder band 700000-799999 is a non-numeric placeholder —
   do not use it.

5. conditions in symptom_signature: use "TODO: identify component" as the
   component_ref placeholder in any [component_ref, state] pair.

OUTPUT RULES
------------
- Emit ONLY a JSON object. No prose, no markdown fences, no explanation.
- The top-level key MUST be "failure_mode".
- Example structure: {{"failure_mode": {{...}}}}
"""


def draft_add(runtime: dict, knowledge: dict) -> dict:
    """
    Pure function (no file I/O, no Supabase). Returns a draft failure_mode dict.

    Raises RuntimeError(raw_text) if the LLM returns non-JSON after one retry
    — the caller should write raw_text to a .RAW.txt file.
    """
    import openai

    _load_env()
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY not set — add it to .env or export it in the shell"
        )
    client = openai.OpenAI(api_key=api_key)

    prompt = _PROMPT_TEMPLATE.format(
        reported        = repr((runtime.get("reported") or "").strip()),
        resolution      = repr((runtime.get("resolution_note") or "").strip()),
        sanity          = repr(" ".join(runtime.get("sanity_notes") or [])),
        checks          = json.dumps(runtime.get("checks") or []),
        confirmed_cause = repr(runtime.get("confirmed_cause") or ""),
    )

    def _call():
        return client.chat.completions.create(
            model="gpt-5.4",
            temperature=0,
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": prompt}],
        )

    raw = None
    try:
        raw = _call().choices[0].message.content
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        try:
            raw = _call().choices[0].message.content
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(raw or str(exc)) from exc

    fm = parsed.get("failure_mode", parsed)

    # Stamp provenance from runtime — never trust LLM for this
    conv_id = runtime.get("id")
    if conv_id:
        fm.setdefault("provenance", [conv_id])
        fm["evidence_count"] = 1

    # Ensure id is set and doesn't look like a placeholder
    if not fm.get("id") or "TODO" in str(fm.get("id", "")):
        existing = {f["id"] for f in knowledge.get("failure_modes", [])}
        fm["id"] = _fm_id(runtime.get("reported", "unknown"), existing)

    return fm


if __name__ == "__main__":
    import argparse
    sys.path.insert(0, str(Path(__file__).parent))

    ap = argparse.ArgumentParser(
        description="Draft a new failure_mode from a declined/ADD session"
    )
    ap.add_argument("--machine-id", default="DMC80FD-01")
    ap.add_argument("--conv-id", default=None,
                    help="conversation_id to fetch from storage")
    ap.add_argument("--runtime-json", default=None,
                    help="path to a local runtime blob (skips storage)")
    ap.add_argument("--knowledge-json", default=None,
                    help="path to a local knowledge.json (skips storage)")
    ap.add_argument("--source", default="bucket", choices=("bucket", "local"))
    ap.add_argument("--local-runtime-dir", default=None)
    ap.add_argument("--local-knowledge-dir", default=None)
    ap.add_argument("--out", default="out")
    ap.add_argument("--env-file", default=None)
    a = ap.parse_args()

    _load_env(a.env_file)

    # ── load runtime ──────────────────────────────────────────────────────────
    if a.runtime_json:
        rt = json.loads(Path(a.runtime_json).read_text())
        conv_id = a.conv_id or Path(a.runtime_json).stem
    elif a.conv_id:
        from storage import StorageClient
        store = StorageClient(
            source=a.source,
            local_runtime_dir=a.local_runtime_dir,
            local_knowledge_dir=a.local_knowledge_dir,
            env_file=a.env_file,
        )
        rt = store.get_runtime(a.machine_id, a.conv_id)
        conv_id = a.conv_id
    else:
        ap.error("one of --conv-id or --runtime-json is required")

    # ── load knowledge ────────────────────────────────────────────────────────
    if a.knowledge_json:
        knowledge = json.loads(Path(a.knowledge_json).read_text())
    elif a.source == "bucket" and not a.runtime_json:
        knowledge = store.get_knowledge(a.machine_id)
    else:
        knowledge = {}

    print(f"draft_add  conv={conv_id}")
    print(f"  reported:         {rt.get('reported')!r}")
    print(f"  resolution_note:  {rt.get('resolution_note')!r}")

    os.makedirs(a.out, exist_ok=True)

    try:
        draft = draft_add(rt, knowledge)
        out_path = os.path.join(a.out, f"add_{conv_id}.draft.json")
        Path(out_path).write_text(json.dumps(draft, indent=2))
        print(f"\n→ wrote {out_path}")
        print(f"  id:               {draft.get('id')}")
        print(f"  component_ref:    {draft.get('component_ref')}")
        print(f"  title:            {draft.get('title')}")
        print(f"  guardrail:        {draft.get('guardrail')}")
        ss = draft.get("symptom_signature") or {}
        print(f"  operator_phrases: {ss.get('operator_phrases', [])}")
        causes = draft.get("causes") or []
        if causes:
            print(f"  cause[0].mechanism: {causes[0].get('mechanism')}")
    except RuntimeError as exc:
        raw_text = str(exc)
        raw_path = os.path.join(a.out, f"add_{conv_id}.draft.RAW.txt")
        Path(raw_path).write_text(raw_text)
        print(f"\nERROR: LLM returned non-JSON after retry.")
        print(f"Raw output written to {raw_path}")
        sys.exit(1)
