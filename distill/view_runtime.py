#!/usr/bin/env python3
"""
view_runtime.py — make runtime.json human-readable.

Renders each runtime.json as a plain-language narrative (leaning on the operator's
verbatim text), resolving slugs against knowledge.json where possible and humanizing
them otherwise. No LLM. Outputs console text + a sessions.html viewer.

Usage:
  python view_runtime.py --runtime sample/real-runtime --knowledge sample/knowledge-DMC80FD-01.json --out out
"""
import argparse, glob, json, os, html, re

PREFIXES = ("fm_", "cause_", "chk_", "proc_", "step_", "warn_")

def load(p):
    with open(p) as f: return json.load(f)

def humanize(slug):
    if not slug: return ""
    s = slug
    for p in PREFIXES:
        if s.startswith(p): s = s[len(p):]; break
    return s.replace("_", " ").strip()

def index_knowledge(k):
    idx = {}
    for coll in ("failure_modes", "checks", "causes", "procedures", "steps", "warnings"):
        for o in (k.get(coll) or []):
            if isinstance(o, dict) and "id" in o:
                idx[o["id"]] = o.get("name") or o.get("text") or humanize(o["id"])
    return idx

def name_of(slug, idx, clarify_titles):
    if not slug: return ""
    if slug in idx: return idx[slug]
    if slug in clarify_titles: return clarify_titles[slug]
    return humanize(slug)

def narrate(rt, idx):
    machine = rt.get("machine", "the machine")
    status = (rt.get("status") or "open").lower()
    reported = (rt.get("reported") or "").strip()
    notes = [n.strip() for n in (rt.get("sanity_notes") or []) if n.strip()]
    checks = rt.get("checks") or []
    clarify = rt.get("_clarify") or []
    clarify_titles = {c.get("id"): c.get("title") for c in clarify if c.get("id")}
    matched = name_of(rt.get("matched_fm"), idx, clarify_titles)
    cause = name_of(rt.get("confirmed_cause"), idx, clarify_titles)
    proc = name_of(rt.get("procedure"), idx, clarify_titles)
    resnote = (rt.get("resolution_note") or "").strip()

    parts = []
    parts.append(f"On {machine}, the operator reported: \u201c{reported}\u201d." if reported
                 else f"On {machine}, a session was opened.")
    if notes:
        parts.append("They added: \u201c" + " ".join(notes) + "\u201d")
    if checks:
        c = checks[0]
        ans = (c.get("answer") or "").strip()
        parts.append(f"Mary had them check the {humanize(c.get('ref',''))} \u2014 they found: \u201c{ans}\u201d." if ans
                     else f"Mary asked them to check the {humanize(c.get('ref',''))}.")
    resolved = status in ("green", "resolved")
    if resolved:
        diag = matched + (f", caused by {cause}" if cause and rt.get("confirmed_cause") else "")
        if diag.strip(): parts.append(f"That pointed to {diag}.")
        if proc and rt.get("procedure"): parts.append(f"Following the \u201c{proc}\u201d procedure,")
        parts.append(f"it was resolved: \u201c{resnote}\u201d" if resnote else "it was resolved.")
    elif clarify:
        opts = "; ".join(c.get("title", "") for c in clarify if c.get("title"))
        parts.append(f"Mary couldn't pin it down yet and offered: {opts}.")
        parts.append("Still open \u2014 no resolution recorded.")
    else:
        parts.append("Still open \u2014 diagnosis in progress, nothing matched yet.")
    # join smartly
    text = " ".join(parts)
    text = re.sub(r"\s+,", ",", text).replace(" .", ".")
    label = {"green":"RESOLVED","resolved":"RESOLVED","open":"OPEN"}.get(status, status.upper())
    return label, text

def render_html(sessions, machine):
    cards = []
    for sid, label, text, rt in sessions:
        cls = "resolved" if label == "RESOLVED" else "open"
        raw = html.escape(json.dumps(rt, indent=2, ensure_ascii=False))
        cards.append(f"""
        <div class="card {cls}">
          <div class="top"><span class="sid">{html.escape(sid)}</span>
            <span class="badge {cls}">{label}</span></div>
          <p class="story">{html.escape(text)}</p>
          <details><summary>raw state</summary><pre>{raw}</pre></details>
        </div>""")
    return HTML_HEAD.replace("__MACHINE__", html.escape(machine)) + "\n".join(cards) + HTML_TAIL

HTML_HEAD = """<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Sessions — __MACHINE__</title>
<style>
 :root{--bg:#14110f;--panel:#1d1916;--ink:#f4efe9;--mut:#b3a99e;--faint:#8a8077;--line:#322b25;
  --green:#5fae7a;--greenln:#27452f;--amber:#d9a441;--amberln:#4a3d1c;--accent:#e8623d;--mono:ui-monospace,Menlo,monospace;}
 *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;line-height:1.6}
 .wrap{max-width:760px;margin:0 auto;padding:28px 20px 70px}
 h1{font-size:22px;margin:0 0 4px}.sub{color:var(--mut);font-size:13px;margin-bottom:20px}
 .card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px 18px;margin:13px 0}
 .card.resolved{border-left:3px solid var(--green)}.card.open{border-left:3px solid var(--amber)}
 .top{display:flex;align-items:center;gap:10px;margin-bottom:8px}
 .sid{font-family:var(--mono);font-size:12px;color:var(--faint)}
 .badge{font-family:var(--mono);font-size:10px;font-weight:700;letter-spacing:.06em;padding:2px 8px;border-radius:5px}
 .badge.resolved{color:var(--green);border:1px solid var(--greenln)}.badge.open{color:var(--amber);border:1px solid var(--amberln)}
 .story{font-size:15.5px;color:var(--ink);margin:4px 0 10px}
 details summary{cursor:pointer;color:var(--faint);font-size:12px;font-family:var(--mono)}
 pre{background:#100d0b;border:1px solid var(--line);border-radius:8px;padding:10px;font-family:var(--mono);font-size:11px;color:var(--mut);overflow:auto;margin-top:8px}
</style></head><body><div class="wrap">
 <h1>Sessions — __MACHINE__</h1>
 <div class="sub">Plain-language view of runtime.json — slugs resolved against knowledge.json, operator words verbatim.</div>"""
HTML_TAIL = "</div></body></html>"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runtime", required=True)
    ap.add_argument("--knowledge", required=True)
    ap.add_argument("--out", default="out")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    idx = index_knowledge(load(a.knowledge))
    files = [a.runtime] if os.path.isfile(a.runtime) else sorted(glob.glob(os.path.join(a.runtime, "*.json")))
    sessions, machine = [], "machine"
    for fp in files:
        rt = load(fp)
        machine = rt.get("machine", machine)
        sid = rt.get("id") or os.path.splitext(os.path.basename(fp))[0]
        label, text = narrate(rt, idx)
        sessions.append((sid, label, text, rt))
        print(f"\n[{label}] {sid}\n{text}")
    with open(os.path.join(a.out, "sessions.html"), "w") as f:
        f.write(render_html(sessions, machine))
    print(f"\n-> {a.out}/sessions.html ({len(sessions)} sessions)")

if __name__ == "__main__":
    main()
