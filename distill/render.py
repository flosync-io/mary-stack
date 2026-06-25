#!/usr/bin/env python3
"""
render.py — shared human-render module for distill.

Public API
----------
name_of(slug, knowledge) -> str
    Resolve a slug against knowledge.json; humanize on miss
    (strip fm_/cause_/chk_/proc_/step_/warn_ prefix, _→space).

narrate(runtime, knowledge) -> str
    One-paragraph plain-language story from a runtime.json.
    Leans on verbatim operator fields (reported, sanity_notes,
    check answers, resolution_note); no LLM.

Both functions are the single source of slug-resolution logic.
view_runtime.py and promote.py import from here; nothing is duplicated.
"""
import re

PREFIXES = ("fm_", "cause_", "chk_", "proc_", "step_", "warn_")


def _humanize(slug):
    if not slug:
        return ""
    s = slug
    for p in PREFIXES:
        if s.startswith(p):
            s = s[len(p):]
            break
    return s.replace("_", " ").strip()


def _index(knowledge):
    idx = {}
    for coll in ("failure_modes", "checks", "causes", "procedures", "steps", "warnings"):
        for o in (knowledge.get(coll) or []):
            if isinstance(o, dict) and "id" in o:
                idx[o["id"]] = o.get("name") or o.get("text") or _humanize(o["id"])
    return idx


def name_of(slug, knowledge):
    """Resolve slug against knowledge.json; humanize on miss."""
    if not slug:
        return ""
    return _index(knowledge).get(slug) or _humanize(slug)


def narrate(runtime, knowledge):
    """
    Return a one-paragraph plain-language story for a runtime.json session.

    Resolution priority for slugs:
      1. knowledge.json index (name / text / humanized id)
      2. _clarify titles from the runtime (fallback for unmatched FMs)
      3. humanize (strip prefix, _→space)
    """
    idx = _index(knowledge)
    rt = runtime

    machine  = rt.get("machine", "the machine")
    status   = (rt.get("status") or "open").lower()
    reported = (rt.get("reported") or "").strip()
    notes    = [n.strip() for n in (rt.get("sanity_notes") or []) if n.strip()]
    checks   = rt.get("checks") or []
    clarify  = rt.get("_clarify") or []
    clarify_titles = {c.get("id"): c.get("title") for c in clarify if c.get("id")}

    def _name(slug):
        if not slug:
            return ""
        if slug in idx:
            return idx[slug]
        if slug in clarify_titles:
            return clarify_titles[slug]
        return _humanize(slug)

    matched  = _name(rt.get("matched_fm"))
    cause    = _name(rt.get("confirmed_cause"))
    proc     = _name(rt.get("procedure"))
    resnote  = (rt.get("resolution_note") or "").strip()

    parts = []
    parts.append(
        f"On {machine}, the operator reported: “{reported}”."
        if reported else f"On {machine}, a session was opened."
    )
    if notes:
        parts.append("They added: “" + " ".join(notes) + "”")
    if checks:
        c   = checks[0]
        ans = (c.get("answer") or "").strip()
        parts.append(
            f"Mary had them check the {_humanize(c.get('ref', ''))} — they found: “{ans}”."
            if ans else
            f"Mary asked them to check the {_humanize(c.get('ref', ''))}."
        )
    resolved = status in ("green", "resolved")
    if resolved:
        diag = matched + (f", caused by {cause}" if cause and rt.get("confirmed_cause") else "")
        if diag.strip():
            parts.append(f"That pointed to {diag}.")
        if proc and rt.get("procedure"):
            parts.append(f"Following the “{proc}” procedure,")
        parts.append(
            f"it was resolved: “{resnote}”" if resnote else "it was resolved."
        )
    elif clarify:
        opts = "; ".join(c.get("title", "") for c in clarify if c.get("title"))
        parts.append(f"Mary couldn’t pin it down yet and offered: {opts}.")
        parts.append("Still open — no resolution recorded.")
    else:
        parts.append("Still open — diagnosis in progress, nothing matched yet.")

    text = " ".join(parts)
    text = re.sub(r"\s+,", ",", text).replace(" .", ".")
    return text
