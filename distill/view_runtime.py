#!/usr/bin/env python3
"""
view_runtime.py — make runtime.json human-readable.

Renders each runtime.json as a plain-language narrative (leaning on the operator's
verbatim text), resolving slugs against knowledge.json where possible and humanizing
them otherwise. No LLM. Outputs console text + a sessions.html viewer.

Slug-resolution and narration logic lives in render.py (single source of truth).

Usage:
  python view_runtime.py --runtime sample/real-runtime --knowledge sample/knowledge-DMC80FD-01.json --out out
"""
import argparse, glob, json, os, html
from render import narrate

def load(p):
    with open(p) as f: return json.load(f)

_STATUS_LABEL = {"green": "RESOLVED", "resolved": "RESOLVED", "open": "OPEN"}

def _label(status):
    s = (status or "open").lower()
    return _STATUS_LABEL.get(s, s.upper())

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
    knowledge = load(a.knowledge)
    files = [a.runtime] if os.path.isfile(a.runtime) else sorted(glob.glob(os.path.join(a.runtime, "*.json")))
    sessions, machine = [], "machine"
    for fp in files:
        rt = load(fp)
        machine = rt.get("machine", machine)
        sid = rt.get("id") or os.path.splitext(os.path.basename(fp))[0]
        text  = narrate(rt, knowledge)
        label = _label(rt.get("status"))
        sessions.append((sid, label, text, rt))
        print(f"\n[{label}] {sid}\n{text}")
    with open(os.path.join(a.out, "sessions.html"), "w") as f:
        f.write(render_html(sessions, machine))
    print(f"\n-> {a.out}/sessions.html ({len(sessions)} sessions)")

if __name__ == "__main__":
    main()
