#!/usr/bin/env python3
"""
promote.py — B-zero promotion: resolved runtime.json -> knowledge.json

Default: dry-run (print only, write nothing).
  --apply: writes version-bumped knowledge.json + decision log to --out.

ADD candidates that can't satisfy the knowledge schema (missing
component_ref, title, guardrail, etc.) are listed as
"deferred — needs authoring" and are never written even with --apply.

Routing:
  resolved + matched_fm in knowledge  -> ENRICH  (provenance+count only)
  resolved + matched_fm contradicts   -> REVISE   (surfaces contradiction)
  resolved + matched_fm null          -> ADD      (new FM skeleton; likely deferred)
  not resolved                        -> skip

Usage:
  python promote.py --knowledge sample/knowledge-DMC80FD-01.json \\
                    --runtime  sample/real-runtime
  python promote.py ... --apply   # writes knowledge.json + decision-log.json
"""
import argparse, json, os, glob, datetime, sys
from render import narrate

RESOLVED_STATUSES = ("green", "resolved")
CONTRADICT_HINTS = ("did not", "didn't", "not hold", "escalat", "recurred", "no longer", "wrong")

# Required by the knowledge schema's failure_mode definition.
# An ADD skeleton can derive 'id' from the symptom; everything else needs human authoring.
FM_SCHEMA_REQUIRED = {"id", "component_ref", "title", "guardrail", "case_count", "symptom_signature", "causes"}


def load(p):
    with open(p) as f:
        return json.load(f)


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
    conv = rt.get("id") or os.path.splitext(os.path.basename(fp))[0]
    op, target = classify(rt, fm_index)

    # idempotency: skip if already promoted
    if op in ("enrich", "revise") and target:
        if conv in fm_index[target].get("provenance", []):
            return None

    grounding = {
        "conversation_id": conv,
        "operator_id": rt.get("operator_id", "?"),
        "narrative": narrate(rt, knowledge),
        "symptom": rt.get("reported", ""),
        "resolution": rt.get("resolution_note", ""),
        "ruled_out": rt.get("ruled_out", []),
    }

    if op == "add":
        fid = new_fm_id(rt.get("reported", "unknown"), fm_index)
        skeleton = {
            "id": fid,
            "name": (rt.get("reported", "")[:60].capitalize()),
            "symptoms": [rt.get("reported", "")],
            "checks": [],
            "resolution": rt.get("resolution_note", ""),
            "escalate": False,
            "provenance": [conv],
            "evidence_count": 1,
        }
        missing = sorted(FM_SCHEMA_REQUIRED - set(skeleton.keys()))
        deferred = bool(missing)
        return {
            "op": "add",
            "target_id": fid,
            "before": None,
            "after": skeleton,
            "grounding": grounding,
            "deferred": deferred,
            "deferred_reason": ("needs authoring: " + ", ".join(missing)) if deferred else None,
        }

    before = json.loads(json.dumps(fm_index[target]))
    after  = json.loads(json.dumps(before))
    if conv not in after.get("provenance", []):
        after.setdefault("provenance", []).append(conv)
    after["evidence_count"] = len(after["provenance"])
    if op == "revise":
        after["resolution"] = rt.get("resolution_note", before.get("resolution", ""))
    return {
        "op": op,
        "target_id": target,
        "before": before,
        "after": after,
        "grounding": grounding,
        "deferred": False,
        "deferred_reason": None,
    }


def field_diff(before, after):
    """Return only the fields that changed, as {key: {before, after}}."""
    if before is None:
        return None
    changed = {}
    for k in set(list(before.keys()) + list(after.keys())):
        b, a = before.get(k), after.get(k)
        if b != a:
            changed[k] = {"before": b, "after": a}
    return changed


def apply_changes(knowledge, changes):
    k = json.loads(json.dumps(knowledge))
    fms = k.setdefault("failure_modes", [])
    idx = {fm["id"]: i for i, fm in enumerate(fms)}
    for ch in changes:
        if ch.get("deferred"):
            continue
        if ch["op"] == "add":
            fms.append(ch["after"])
        elif ch["target_id"] in idx:
            fms[idx[ch["target_id"]]] = ch["after"]
    return k


def bump_version(knowledge):
    meta = dict(knowledge.get("_meta") or {})
    prev = meta.get("version")
    today = datetime.date.today().isoformat()
    if prev and prev.startswith(today + "."):
        try:
            n = int(prev.rsplit(".", 1)[-1]) + 1
        except ValueError:
            n = 2
    else:
        n = 1
    meta["parent_version"] = prev
    meta["version"] = f"{today}.{n}"
    knowledge["_meta"] = meta
    return knowledge


def validate_schema(knowledge, schema_path):
    """Return list of error messages, or [] if valid (or jsonschema not installed)."""
    if not os.path.exists(schema_path):
        return []
    try:
        from jsonschema import Draft202012Validator
        errs = list(Draft202012Validator(load(schema_path)).iter_errors(knowledge))
        return [e.message for e in errs]
    except ImportError:
        return []


def print_change(ch, i, total):
    op  = ch["op"].upper()
    tid = ch["target_id"]
    g   = ch["grounding"]

    print(f"\n── [{i}/{total}] {op}  {tid}")
    print(f"   narrative : {g['narrative']}")

    if ch.get("deferred"):
        print(f"   DEFERRED  — {ch['deferred_reason']}")
        return

    diff = field_diff(ch["before"], ch["after"])
    if diff is None:
        # ADD (non-deferred would be unusual but handle gracefully)
        print("   skeleton  :")
        for k, v in ch["after"].items():
            print(f"     {k}: {json.dumps(v)}")
    else:
        print("   diff      :")
        for k, d in diff.items():
            print(f"     {k}:  {json.dumps(d['before'])}  →  {json.dumps(d['after'])}")


def main():
    ap = argparse.ArgumentParser(description="Promote resolved sessions -> knowledge.json")
    ap.add_argument("--knowledge", required=True)
    ap.add_argument("--runtime", required=True, help="resolved runtime.json file or dir of them")
    ap.add_argument("--out", default="out", help="output directory (used only with --apply)")
    ap.add_argument("--schema", default=None, help="path to contracts/schema.json")
    ap.add_argument("--apply", action="store_true",
                    help="write new knowledge.json + decision log (dry-run if omitted)")
    a = ap.parse_args()

    knowledge = load(a.knowledge)
    machine   = knowledge.get("_meta", {}).get("machine_id", "unknown")
    fm_index  = {fm["id"]: fm for fm in knowledge.get("failure_modes", [])}

    all_files = (
        [a.runtime] if os.path.isfile(a.runtime)
        else sorted(glob.glob(os.path.join(a.runtime, "*.json")))
    )
    total_sessions = len(all_files)
    resolved = resolved_runtimes(a.runtime)
    skipped_open = total_sessions - len(resolved)

    raw     = [build_change(fp, rt, fm_index, knowledge) for fp, rt in resolved]
    already = sum(1 for c in raw if c is None)
    changes = [c for c in raw if c is not None]

    active   = [c for c in changes if not c.get("deferred")]
    deferred = [c for c in changes if c.get("deferred")]

    # ── header ──
    print(f"promote.py — {machine}  ({datetime.date.today().isoformat()})")
    print(
        f"sessions: {total_sessions} total · {len(resolved)} resolved · "
        f"{skipped_open} skipped (not resolved) · {already} already promoted"
    )

    # ── per-change output ──
    for i, ch in enumerate(changes, 1):
        print_change(ch, i, len(changes))

    # ── summary ──
    counts = {}
    for c in active:
        counts[c["op"]] = counts.get(c["op"], 0) + 1

    parts = []
    for op in ("enrich", "revise", "add"):
        if op in counts:
            parts.append(f"{counts[op]} {op}")
    if deferred:
        parts.append(f"{len(deferred)} deferred (needs authoring)")
    parts.append(f"{skipped_open + already} skipped")

    print(f"\n{'─' * 60}")
    print("  " + " · ".join(parts))

    # ── apply ──
    if a.apply:
        os.makedirs(a.out, exist_ok=True)
        candidate = bump_version(apply_changes(knowledge, changes))

        errs = validate_schema(candidate, a.schema) if a.schema else []
        if errs:
            print(f"\nSchema validation FAILED — not writing:")
            for e in errs[:5]:
                print(f"  {e}")
            sys.exit(1)

        kb_out  = os.path.join(a.out, f"knowledge-{machine}.json")
        log_out = os.path.join(a.out, f"decision-log-{datetime.date.today().isoformat()}.json")

        with open(kb_out, "w") as f:
            json.dump(candidate, f, indent=2)
        # reference files for tooling / tests
        with open(os.path.join(a.out, "candidate.json"), "w") as f:
            json.dump(candidate, f, indent=2)
        with open(os.path.join(a.out, "changes.json"), "w") as f:
            json.dump(changes, f, indent=2)

        log = {
            "machine": machine,
            "at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "parent_version": knowledge.get("_meta", {}).get("version"),
            "new_version": candidate["_meta"]["version"],
            "applied": len(active),
            "deferred": len(deferred),
            "decisions": [
                {
                    "target": c["target_id"],
                    "op": c["op"],
                    "deferred": c.get("deferred", False),
                    "deferred_reason": c.get("deferred_reason"),
                }
                for c in changes
            ],
        }
        with open(log_out, "w") as f:
            json.dump(log, f, indent=2)

        print(f"\n--apply: wrote {kb_out}  (version {candidate['_meta']['version']})")
        print(f"         wrote {log_out}")
    else:
        print(f"\n(dry-run — pass --apply to write knowledge.json + decision log)")


if __name__ == "__main__":
    main()
