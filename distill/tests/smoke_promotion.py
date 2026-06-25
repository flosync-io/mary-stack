#!/usr/bin/env python3
"""
End-to-end smoke test for the promotion loop: runtime.json -> knowledge.json.
Builds controlled fixtures, runs the REAL promote.py, asserts the architectural
invariants. Catches drift between the intended design and the implementation.

Run from repo root:  python3 distill/tests/smoke_promotion.py
"""
import json, os, subprocess, sys, tempfile, shutil

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PROMOTE = os.path.join(ROOT, "distill", "promote.py")
SCHEMA  = os.path.join(ROOT, "contracts", "schema.json")

FAILS = []
def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (f"   -> {detail}" if detail and not cond else ""))
    if not cond: FAILS.append(name)

# ---- controlled starting knowledge.json (provenance/count CONSISTENT: count == len(provenance)) ----
BASE_KB = {
  "_meta": {"machine_id": "DMC80FD-01", "version": "test.0", "parent_version": None},
  "failure_modes": [
    {"id": "fm_coolant_concentration_low", "name": "Coolant concentration low",
     "symptoms": ["overheating during cut", "poor finish"], "checks": ["chk_coolant_condition"],
     "procedure": "proc_check_correct_coolant_concentration",
     "resolution": "Check coolant condition and concentration; correct premix to spec.",
     "escalate": False, "provenance": ["c0001"], "evidence_count": 1},
    {"id": "fm_axis_drift", "name": "Axis position drift",
     "symptoms": ["part out of tolerance"], "checks": ["chk_rehome"],
     "procedure": "proc_rehome", "resolution": "Re-home the axis and continue.",
     "escalate": False, "provenance": ["c0002"], "evidence_count": 1}
  ],
  "checks": [{"id": "chk_coolant_condition", "text": "x"}, {"id": "chk_rehome", "text": "x"}]
}

def rt(status, matched_fm, reported, resolution_note, confirmed_cause=None):
    return {"id": None, "machine": "DMC80FD-01", "status": status, "reported": reported,
            "checks": [], "attempts": [], "matched_fm": matched_fm,
            "confirmed_cause": confirmed_cause, "resolution_note": resolution_note,
            "$soul_version": "draft"}

FIX = {
  "sess_enrich.json": rt("green", "fm_coolant_concentration_low", "machine hot, red light",
                         "added premix, back to spec", "cause_coolant_low_concentration"),
  "sess_add.json":    rt("green", None, "spindle grinding fixed by drawbar", "torqued drawbar, noise gone"),
  "sess_revise.json": rt("green", "fm_axis_drift", "X drifting again",
                         "re-home did NOT hold; recurred; escalated to maintenance - bearing wear"),
  "sess_open.json":   rt("open", None, "press jamming", None),
}

def run(kb_path, rt_dir, out_dir):
    r = subprocess.run([sys.executable, PROMOTE, "--knowledge", kb_path, "--runtime", rt_dir, "--out", out_dir, "--apply"],
                       cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        print("promote.py FAILED to run:\n", r.stderr); sys.exit(2)
    cand = json.load(open(os.path.join(out_dir, "candidate.json")))
    chp = os.path.join(out_dir, "changes.json")
    changes = json.load(open(chp)) if os.path.exists(chp) else None
    return cand, changes

def fm_of(kb, fid): return next((f for f in kb["failure_modes"] if f["id"] == fid), None)

def main():
    tmp = tempfile.mkdtemp()
    kb_path = os.path.join(tmp, "kb.json"); json.dump(BASE_KB, open(kb_path, "w"), indent=2)
    rt_dir = os.path.join(tmp, "runtime"); os.makedirs(rt_dir)
    for n, d in FIX.items(): json.dump(d, open(os.path.join(rt_dir, n), "w"), indent=2)

    cand, changes = run(kb_path, rt_dir, os.path.join(tmp, "out1"))

    if changes is not None:
        ops = sorted(c.get("op") for c in changes)
        check("routing: enrich + add + revise (1 each), open skipped",
              ops == ["add", "enrich", "revise"], f"got {ops}")
    else:
        print("NOTE: no changes.json emitted - routing inferred from candidate only")

    base = fm_of(BASE_KB, "fm_coolant_concentration_low")
    enr  = fm_of(cand,    "fm_coolant_concentration_low")
    check("ENRICH appends provenance (keeps c0001, len 2)",
          enr["provenance"][0] == "c0001" and len(enr["provenance"]) == 2, f"{enr['provenance']}")
    check("ENRICH evidence_count == len(provenance)",
          enr["evidence_count"] == len(enr["provenance"]), f"count={enr['evidence_count']} prov={enr['provenance']}")
    cks = ["name", "symptoms", "checks", "procedure", "resolution", "escalate"]
    check("ENRICH leaves FM content unchanged (provenance+count only)",
          all(enr[k] == base[k] for k in cks),
          "; ".join(f"{k}:{base[k]!r}->{enr[k]!r}" for k in cks if enr[k] != base[k]))
    check("ENRICH adds no field_notes", "field_notes" not in enr, str(enr.get("field_notes")))

    # ADD can't satisfy schema (missing component_ref/title/guardrail) -> deferred, not written
    add_changes = [c for c in (changes or []) if c.get("op") == "add"]
    check("ADD is proposed (in changes.json) and deferred (not written to candidate)",
          len(add_changes) == 1 and add_changes[0].get("deferred") is True,
          f"add_changes: {add_changes}")
    new_ids = {f["id"] for f in cand["failure_modes"]} - {f["id"] for f in BASE_KB["failure_modes"]}
    check("ADD deferred -> no new failure_mode in candidate", len(new_ids) == 0, f"new: {new_ids}")

    try:
        from jsonschema import Draft202012Validator as V
        errs = list(V(json.load(open(SCHEMA))).iter_errors(cand))
        check("candidate.json validates against contracts/schema.json", not errs,
              "; ".join(e.message for e in errs[:3]))
    except ImportError:
        print("SKIP schema validation (pip install jsonschema)")

    # idempotence: feed candidate back as knowledge, re-run; already-promoted session must not re-apply
    c1 = os.path.join(tmp, "cand1.json"); json.dump(cand, open(c1, "w"))
    cand2, _ = run(c1, rt_dir, os.path.join(tmp, "out2"))
    e2 = fm_of(cand2, "fm_coolant_concentration_low")
    check("IDEMPOTENT: re-run does not duplicate provenance",
          e2["provenance"] == enr["provenance"], f"{enr['provenance']} -> {e2['provenance']}")
    check("IDEMPOTENT: re-run does not bump evidence_count",
          e2["evidence_count"] == enr["evidence_count"], f"{enr['evidence_count']} -> {e2['evidence_count']}")

    shutil.rmtree(tmp)
    print("\n" + ("ALL PASS" if not FAILS else f"{len(FAILS)} FAILED: " + ", ".join(FAILS)))
    sys.exit(1 if FAILS else 0)

if __name__ == "__main__":
    main()
