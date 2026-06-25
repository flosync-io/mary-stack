#!/usr/bin/env python3
"""
promote.py — B-zero promotion: resolved runtime.json -> candidate knowledge.json + review.html

What it does (no LLM, deterministic — runtime.json is already typed by the engine):
  1. Loads the current knowledge.json.
  2. For each RESOLVED runtime.json, derives one proposed change:
       - resolved + matched_fm present in knowledge.json -> ENRICH  (+provenance, +count; no content rewrite)
         ...promoted to REVISE (flagged) if resolution_note hints a contradiction
       - resolved + matched_fm null                      -> ADD     (new FM skeleton)
       - not resolved                                    -> skip
  3. Writes changes.json + candidate.json (all changes applied, for reference).
  4. Generates review.html — the human (Denver) reviews, edits inline, approves;
     on approve the browser downloads the new, version-bumped knowledge.json + a decision log.

Real runtime shape (ADR-0001):
  status      "green" | "open" (real files); schema target is "resolved" | "open" | "unresolved"
  matched_fm  slug or null
  confirmed_cause slug or null
  resolution_note operator's closing words
  id          null today — use filename as conversation_id

Usage:
  python promote.py --knowledge sample/knowledge-DMC80FD-01.json \\
                    --runtime  sample/real-runtime \\
                    --out      out
"""
import argparse, json, os, glob, datetime, html
from render import narrate

# TODO: reconcile green→resolved at the N15 writer (ADR-0001 action 5)
RESOLVED_STATUSES = ("green", "resolved")

CONTRADICT_HINTS = ("did not", "didn't", "not hold", "didn't", "escalat", "recurred", "no longer", "wrong")


def load(p):
    with open(p) as f: return json.load(f)


def resolved_runtimes(path):
    files = [path] if os.path.isfile(path) else sorted(glob.glob(os.path.join(path, "*.json")))
    out = []
    for fp in files:
        d = load(fp)
        if d.get("status") in RESOLVED_STATUSES:
            out.append((fp, d))
    return out


def classify(rt, fm_index):
    matched_fm = rt.get("matched_fm")
    resolution_note = (rt.get("resolution_note") or "").lower()
    if matched_fm and matched_fm in fm_index:
        contradicts = any(h in resolution_note for h in CONTRADICT_HINTS)
        return ("revise" if contradicts else "enrich"), matched_fm
    return "add", None


def new_fm_id(symptom, existing):
    base = "fm_" + "_".join("".join(c for c in w if c.isalnum()) for w in symptom.lower().split()[:3])
    cand, i = base, 2
    while cand in existing:
        cand = f"{base}_{i}"; i += 1
    return cand


def build_change(fp, rt, fm_index, knowledge):
    # conversation_id = filename since id is null in real files (ADR-0001)
    conv = rt.get("id") or os.path.splitext(os.path.basename(fp))[0]
    op, target = classify(rt, fm_index)
    grounding = {
        "conversation_id": conv,
        "operator_id": rt.get("operator_id", "?"),
        "narrative": narrate(rt, knowledge),   # human story via render.py
        "symptom": rt.get("reported", ""),
        "resolution": rt.get("resolution_note", ""),
        "ruled_out": rt.get("ruled_out", []),
    }
    if op == "add":
        fid = new_fm_id(rt.get("reported", "unknown"), fm_index)
        after = {
            "id": fid,
            "name": (rt.get("reported", "")[:60].capitalize()),
            "symptoms": [rt.get("reported", "")],
            "checks": [],
            "resolution": rt.get("resolution_note", ""),
            "escalate": False,
            "provenance": [conv],
            "evidence_count": 1,
        }
        return {"op": "add", "target_id": fid, "before": None, "after": after, "grounding": grounding}

    before = json.loads(json.dumps(fm_index[target]))  # deep copy
    after  = json.loads(json.dumps(before))
    if conv not in after.get("provenance", []):
        after.setdefault("provenance", []).append(conv)
    after["evidence_count"] = after.get("evidence_count", 0) + 1
    if op == "revise":
        # REVISE: surface the contradiction; Denver decides the final wording
        after["resolution"] = rt.get("resolution_note", before.get("resolution", ""))
    return {"op": op, "target_id": target, "before": before, "after": after, "grounding": grounding}


def apply_changes(knowledge, changes, approved_ids=None):
    k = json.loads(json.dumps(knowledge))
    fms = k.setdefault("failure_modes", [])
    idx = {fm["id"]: i for i, fm in enumerate(fms)}
    for ch in changes:
        if approved_ids is not None and ch["target_id"] not in approved_ids:
            continue
        if ch["op"] == "add":
            fms.append(ch["after"])
        else:
            if ch["target_id"] in idx:
                fms[idx[ch["target_id"]]] = ch["after"]
    return k


def render_html(knowledge, changes, machine):
    payload = json.dumps({"base": knowledge, "changes": changes, "machine": machine})
    today = datetime.date.today().isoformat()
    tmpl = HTML_TEMPLATE
    tmpl = tmpl.replace("__PAYLOAD__", payload)
    tmpl = tmpl.replace("__MACHINE__", html.escape(machine))
    tmpl = tmpl.replace("__DATE__", today)
    tmpl = tmpl.replace("__N__", str(len(changes)))
    return tmpl


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--knowledge", required=True)
    ap.add_argument("--runtime", required=True, help="resolved runtime.json file or dir of them")
    ap.add_argument("--out", default="out")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    knowledge = load(a.knowledge)
    machine   = knowledge.get("_meta", {}).get("machine_id", "unknown")
    fm_index  = {fm["id"]: fm for fm in knowledge.get("failure_modes", [])}

    resolved = resolved_runtimes(a.runtime)
    total    = len(list(
        load(fp) for fp in (
            [a.runtime] if os.path.isfile(a.runtime)
            else sorted(glob.glob(os.path.join(a.runtime, "*.json")))
        )
    ))
    skipped  = total - len(resolved)

    changes = [build_change(fp, rt, fm_index, knowledge) for fp, rt in resolved]

    with open(os.path.join(a.out, "changes.json"), "w") as f:
        json.dump(changes, f, indent=2)
    with open(os.path.join(a.out, "candidate.json"), "w") as f:
        json.dump(apply_changes(knowledge, changes), f, indent=2)
    with open(os.path.join(a.out, "review.html"), "w") as f:
        f.write(render_html(knowledge, changes, machine))

    counts = {}
    for c in changes: counts[c["op"]] = counts.get(c["op"], 0) + 1
    summary = ", ".join(f"{v} {k}" for k, v in counts.items()) if counts else "none"
    print(f"{len(changes)} proposed change(s): {summary}  |  {skipped} skipped (not resolved)")
    print(f"  out/review.html     <- open this; Denver reviews + approves")
    print(f"  out/candidate.json  <- all changes applied (reference)")
    print(f"  out/changes.json    <- the structured proposals")


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>knowledge.json review — __MACHINE__</title>
<style>
 :root{--bg:#14110f;--panel:#1d1916;--panel2:#241f1b;--ink:#f4efe9;--mut:#b3a99e;--faint:#8a8077;
  --line:#322b25;--add:#5fae7a;--addbg:#16241c;--enr:#6fa8d6;--enrbg:#141d24;--rev:#d9a441;--revbg:#2a2413;
  --accent:#e8623d;--mono:ui-monospace,Menlo,Consolas,monospace;--sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;}
 *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--sans);line-height:1.5}
 .wrap{max-width:920px;margin:0 auto;padding:26px 20px 120px}
 .eyebrow{font-family:var(--mono);font-size:11px;letter-spacing:.2em;text-transform:uppercase;color:var(--accent)}
 h1{font-size:24px;margin:8px 0 2px;letter-spacing:-.01em}
 .sub{color:var(--mut);font-size:13px;margin-bottom:20px}
 .card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px 17px;margin:12px 0}
 .card.revise{border-color:#5a4a1e}
 .top{display:flex;align-items:center;gap:10px;margin-bottom:10px}
 .badge{font-family:var(--mono);font-size:10.5px;font-weight:700;letter-spacing:.06em;padding:3px 9px;border-radius:6px;text-transform:uppercase}
 .badge.add{background:var(--addbg);color:var(--add);border:1px solid #27452f}
 .badge.enrich{background:var(--enrbg);color:var(--enr);border:1px solid #2a3d50}
 .badge.revise{background:var(--revbg);color:var(--rev);border:1px solid #4a3d1c}
 .tid{font-family:var(--mono);font-size:13px;color:var(--ink)}
 .warn{margin-left:auto;color:var(--rev);font-size:12px;font-family:var(--mono)}
 .ground{background:var(--panel2);border:1px solid var(--line);border-radius:8px;padding:9px 11px;font-size:12.5px;color:var(--mut);margin-bottom:10px}
 .ground b{color:var(--ink);font-weight:600}
 .ground .story{color:var(--ink);font-style:italic;margin:5px 0 3px;display:block}
 .cols{display:grid;grid-template-columns:1fr 1fr;gap:10px}
 @media(max-width:680px){.cols{grid-template-columns:1fr}}
 .collbl{font-family:var(--mono);font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:var(--faint);margin-bottom:4px}
 pre{background:#100d0b;border:1px solid var(--line);border-radius:8px;padding:10px;font-family:var(--mono);font-size:11.5px;color:var(--mut);overflow:auto;margin:0;max-height:230px}
 textarea{width:100%;background:#100d0b;border:1px solid var(--line);border-radius:8px;padding:10px;font-family:var(--mono);font-size:11.5px;color:var(--ink);min-height:160px;resize:vertical}
 .row{display:flex;align-items:center;gap:8px;margin-top:10px}
 .row input[type=checkbox]{width:17px;height:17px;accent-color:var(--accent)}
 .row label{font-size:13px;color:var(--ink)}
 .bar{position:fixed;left:0;right:0;bottom:0;background:#191512;border-top:1px solid var(--line);padding:12px 20px;display:flex;gap:12px;align-items:center;justify-content:flex-end;flex-wrap:wrap}
 .bar .who{margin-right:auto;display:flex;align-items:center;gap:8px;color:var(--mut);font-size:13px}
 .bar input[type=text]{background:#100d0b;border:1px solid var(--line);border-radius:7px;padding:7px 10px;color:var(--ink);font-family:var(--mono);font-size:12px}
 .btn{font-family:var(--sans);font-size:13px;font-weight:600;padding:9px 16px;border-radius:8px;border:1px solid var(--line);background:var(--panel2);color:var(--ink);cursor:pointer}
 .btn.primary{background:var(--accent);border-color:var(--accent);color:#fff}
 .count{font-family:var(--mono);font-size:12px;color:var(--faint)}
</style></head><body><div class="wrap">
 <div class="eyebrow">Flosync · Machine Mary · knowledge promotion</div>
 <h1>Review proposed changes — __MACHINE__</h1>
 <div class="sub">__N__ change(s) distilled from resolved sessions · __DATE__ · approve, edit, or skip each, then download the new knowledge.json</div>
 <div id="cards"></div>
</div>
<div class="bar">
 <span class="who">Reviewer <input type="text" id="who" value="Denver"></span>
 <span class="count" id="count"></span>
 <button class="btn" onclick="selectAll(false)">Skip all</button>
 <button class="btn" onclick="selectAll(true)">Select all</button>
 <button class="btn primary" onclick="approve()">Approve selected &amp; download knowledge.json</button>
</div>
<script>
const DATA = __PAYLOAD__;
const opClass = {add:"add", enrich:"enrich", revise:"revise"};
function esc(s){return (s+"").replace(/[&<>]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));}
function pj(o){return JSON.stringify(o,null,2);}
function render(){
 const host=document.getElementById("cards");
 DATA.changes.forEach((ch,i)=>{
  const card=document.createElement("div");
  card.className="card"+(ch.op==="revise"?" revise":"");
  const g=ch.grounding;
  const defChecked = ch.op!=="revise";
  const beforeBlock = ch.before ? `<div><div class="collbl">before</div><pre>${esc(pj(ch.before))}</pre></div>` : "";
  card.innerHTML=`
   <div class="top">
     <span class="badge ${opClass[ch.op]}">${ch.op}</span>
     <span class="tid">${esc(ch.target_id)}</span>
     ${ch.op==="revise"?'<span class="warn">⚠ changes existing guidance — read carefully</span>':''}
   </div>
   <div class="ground">
     from <b>${esc(g.conversation_id)}</b> · operator: ${esc(g.operator_id)}<br>
     <span class="story">${esc(g.narrative)}</span>
   </div>
   <div class="cols">
     ${beforeBlock}
     <div><div class="collbl">${ch.before?"after (editable)":"new object (editable)"}</div>
       <textarea id="ta${i}">${esc(pj(ch.after))}</textarea></div>
   </div>
   <div class="row"><input type="checkbox" id="ck${i}" ${defChecked?"checked":""} onchange="tally()">
     <label for="ck${i}">${ch.op==="add"?"Add this":ch.op==="revise"?"Apply this revision":"Apply this enrichment"}</label></div>`;
  host.appendChild(card);
 });
 tally();
}
function selectAll(v){DATA.changes.forEach((_,i)=>document.getElementById("ck"+i).checked=v);tally();}
function tally(){
 let n=0;DATA.changes.forEach((_,i)=>{if(document.getElementById("ck"+i).checked)n++;});
 document.getElementById("count").textContent=n+" of "+DATA.changes.length+" selected";
}
function approve(){
 const k=JSON.parse(JSON.stringify(DATA.base));
 k.failure_modes=k.failure_modes||[];
 const idx={};k.failure_modes.forEach((fm,j)=>idx[fm.id]=j);
 const log=[];let applied=0;
 DATA.changes.forEach((ch,i)=>{
  const checked=document.getElementById("ck"+i).checked;
  let obj=null,err=null;
  try{obj=JSON.parse(document.getElementById("ta"+i).value);}catch(e){err=e.message;}
  if(!checked){log.push({target:ch.target_id,op:ch.op,decision:"skipped"});return;}
  if(err){alert("Change "+ch.target_id+": JSON is invalid — fix it before approving.\n"+err);throw err;}
  if(ch.op==="add"){k.failure_modes.push(obj);}
  else{if(ch.target_id in idx)k.failure_modes[idx[ch.target_id]]=obj;else k.failure_modes.push(obj);}
  const edited=JSON.stringify(obj)!==JSON.stringify(ch.after);
  log.push({target:ch.target_id,op:ch.op,decision:"approved",edited:edited});applied++;
 });
 const who=document.getElementById("who").value||"unknown";
 const stamp=new Date().toISOString();
 const prev=(k._meta&&k._meta.version)||null;
 k._meta=Object.assign({},k._meta,{
   parent_version:prev,
   version:new Date().toISOString().slice(0,10)+"."+Math.random().toString(36).slice(2,5),
   approved_by:who, approved_at:stamp
 });
 download("knowledge-"+DATA.machine+".json",pj(k));
 download("decision-log-"+stamp.slice(0,10)+".json",pj({machine:DATA.machine,reviewer:who,at:stamp,
   parent_version:prev,new_version:k._meta.version,applied:applied,decisions:log}));
 alert("Approved "+applied+" change(s) by "+who+".\nDownloaded the new knowledge.json (version "+k._meta.version+") + decision log.\nCommit knowledge.json to version it; git revert to roll back.");
}
function download(name,text){
 const b=new Blob([text],{type:"application/json"});const u=URL.createObjectURL(b);
 const a=document.createElement("a");a.href=u;a.download=name;a.click();URL.revokeObjectURL(u);
}
render();
</script></body></html>
"""

if __name__ == "__main__":
    main()
