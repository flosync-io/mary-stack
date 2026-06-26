#!/usr/bin/env python3
"""
promote.py — B-zero promotion: resolved runtime.json -> knowledge.json

Default: dry-run (print only, write nothing).
  --apply: writes version-bumped knowledge.json + decision log to --out,
           and stamps the vault ledger (mark_promoted) for bucket sessions.

ADD candidates route through an LLM drafter (draft_add): dry-run writes a
human-authorable draft to out/add_<conv>.draft.json (never auto-inserted — it
carries unfilled TODO sentinels). --apply merges a draft as a NEW failure_mode
only once its TODOs are filled and it passes schema validation; otherwise it is
blocked and skipped (ENRICH/REVISE still apply).

Routing:
  resolved + matched_fm in knowledge  -> ENRICH  (provenance+count only)
  resolved + matched_fm contradicts   -> REVISE   (surfaces contradiction)
  resolved + matched_fm null          -> ADD      (new FM skeleton; likely deferred)
  not resolved                        -> skip

Input modes:
  Bucket (default): sessions come from storage.list_promotable(machine_id);
    blobs fetched via storage.get_runtime(); knowledge via storage.get_knowledge().
    --apply also calls storage.mark_promoted() to stamp the vault ledger.

  Local (--source local OR legacy --knowledge/--runtime flags):
    reads files directly. mark_promoted is a no-op. Smoke test uses this path.

Usage:
  # bucket (live Supabase)
  python promote.py --machine-id DMC80FD-01
  python promote.py --machine-id DMC80FD-01 --apply

  # local / legacy (smoke test)
  python promote.py --knowledge sample/knowledge-DMC80FD-01.json \\
                    --runtime  sample/real-runtime
  python promote.py ... --apply
"""
import argparse, json, os, glob, datetime, sys
from render import narrate

RESOLVED_STATUSES = ("green", "resolved")
CONTRADICT_HINTS = ("did not", "didn't", "not hold", "escalat", "recurred", "no longer", "wrong")

# Any draft still containing this substring has a field the human must author
# (emitted by draft_add). Such a draft is incomplete and must not be merged.
TODO_SENTINEL = "TODO: human must author"


def load(p):
    with open(p) as f:
        return json.load(f)


def resolved_runtimes(path):
    """Legacy: scan local files and return (conv_id, dict) pairs that are resolved."""
    files = [path] if os.path.isfile(path) else sorted(glob.glob(os.path.join(path, "*.json")))
    out = []
    for fp in files:
        d = load(fp)
        if d.get("status") in RESOLVED_STATUSES:
            conv_id = os.path.splitext(os.path.basename(fp))[0]
            out.append((conv_id, d))
    return out, len(files)


def classify(rt, fm_index):
    matched_fm = rt.get("matched_fm")
    resolution_note = (rt.get("resolution_note") or "").lower()
    if matched_fm and matched_fm in fm_index:
        contradicts = any(h in resolution_note for h in CONTRADICT_HINTS)
        return ("revise" if contradicts else "enrich"), matched_fm
    return "add", None


def new_fm_id(symptom, existing):
    base = "fm_" + "_".join("".join(c for c in w if c.isalnum())
                             for w in symptom.lower().split()[:3])
    cand, i = base, 2
    while cand in existing:
        cand = f"{base}_{i}"; i += 1
    return cand


def build_change(conv_id, rt, fm_index, knowledge):
    op, target = classify(rt, fm_index)

    # idempotency: skip if already promoted
    if op in ("enrich", "revise") and target:
        if conv_id in fm_index[target].get("provenance", []):
            return None

    grounding = {
        "conversation_id": conv_id,
        "operator_id": rt.get("operator_id", "?"),
        "narrative": narrate(rt, knowledge),
        "symptom": rt.get("reported", ""),
        "resolution": rt.get("resolution_note", ""),
        "ruled_out": rt.get("ruled_out", []),
    }

    if op == "add":
        fid = new_fm_id(rt.get("reported", "unknown"), fm_index)
        # ADD is never auto-applied. The FM body must be human-authored from an
        # LLM draft (draft_add) and merged on --apply only after its TODOs are
        # filled. We carry the runtime so the dry-run can draft it, and keep
        # deferred=True so apply_changes never appends an un-authored skeleton.
        return {
            "op": "add",
            "target_id": fid,
            "before": None,
            "after": None,
            "grounding": grounding,
            "runtime": rt,
            "deferred": True,
            "deferred_reason": "ADD — draft must be human-authored before merge",
        }

    before = json.loads(json.dumps(fm_index[target]))
    after  = json.loads(json.dumps(before))
    if conv_id not in after.get("provenance", []):
        after.setdefault("provenance", []).append(conv_id)
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
    if not os.path.exists(schema_path):
        return []
    try:
        from jsonschema import Draft202012Validator
        errs = list(Draft202012Validator(load(schema_path)).iter_errors(knowledge))
        return [e.message for e in errs]
    except ImportError:
        return []


def validate_fm(fm, schema_path):
    """Schema-validate a single failure_mode draft against contracts/schema.json.

    Wraps the FM in {"failure_modes": [fm]} so the schema's $ref resolves, then
    returns the list of validation error messages ([] = valid). Returns [] (and
    so can't gate) only if the schema file is absent or jsonschema isn't installed.
    """
    if not schema_path or not os.path.exists(schema_path):
        return []
    try:
        from jsonschema import Draft202012Validator
        schema = load(schema_path)
        errs = Draft202012Validator(schema).iter_errors({"failure_modes": [fm]})
        return [e.message for e in errs]
    except ImportError:
        return []


def load_completed_draft(draft_path, schema_path):
    """Gate a human-completed ADD draft before merge.

    Returns (fm_dict, None) when the draft exists, has no unfilled TODO
    sentinels, and validates against the failure_mode schema. Otherwise returns
    (None, reason) — the caller blocks and skips it. This is the gate that makes
    the human-authoring step mandatory.
    """
    if not os.path.exists(draft_path):
        return None, "draft not found (run dry-run first, then author the TODOs)"
    try:
        draft = load(draft_path)
    except (json.JSONDecodeError, OSError) as exc:
        return None, f"unreadable draft ({exc})"
    if TODO_SENTINEL in json.dumps(draft):
        return None, "unfilled TODOs"
    errs = validate_fm(draft, schema_path)
    if errs:
        return None, f"schema-invalid ({errs[0]})"
    return draft, None


def write_add_draft(ch, knowledge, out_dir):
    """Dry-run: draft a new FM via the LLM and write out/add_<conv>.draft.json.

    Returns (draft_path, None) on success or (draft_path, error_msg) on failure
    (missing OPENAI_API_KEY, an LLM parse error, etc.) — the run continues either
    way so other changes still report. The draft is NOT inserted into knowledge.
    """
    conv = ch["grounding"]["conversation_id"]
    draft_path = os.path.join(out_dir, f"add_{conv}.draft.json")
    try:
        from draft_add import draft_add
        draft = draft_add(ch["runtime"], knowledge)
    except Exception as exc:
        return draft_path, str(exc)
    os.makedirs(out_dir, exist_ok=True)
    with open(draft_path, "w") as f:
        json.dump(draft, f, indent=2)
    return draft_path, None


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
        print("   skeleton  :")
        for k, v in ch["after"].items():
            print(f"     {k}: {json.dumps(v)}")
    else:
        print("   diff      :")
        for k, d in diff.items():
            print(f"     {k}:  {json.dumps(d['before'])}  →  {json.dumps(d['after'])}")


def main():
    ap = argparse.ArgumentParser(description="Promote resolved sessions -> knowledge.json")
    ap.add_argument("--machine-id", default="DMC80FD-01",
                    help="machine ID (bucket mode; also used as the knowledge machine label)")
    ap.add_argument("--source", default="bucket", choices=("bucket", "local"),
                    help="bucket: fetch from Supabase; local: use --knowledge/--runtime files")
    ap.add_argument("--env-file", default=None, help="path to .env (bucket mode)")
    # legacy / local-mode args (still required when --source local or --knowledge is given)
    ap.add_argument("--knowledge", default=None,
                    help="explicit knowledge.json path (overrides storage; implies local read)")
    ap.add_argument("--runtime", default=None,
                    help="runtime dir or file (overrides storage; implies local read)")
    ap.add_argument("--out", default="out", help="output directory (used only with --apply)")
    ap.add_argument("--schema", default=None, help="path to contracts/schema.json")
    ap.add_argument("--apply", action="store_true",
                    help="write new knowledge.json + decision log (dry-run if omitted)")
    a = ap.parse_args()

    # ── decide input mode ─────────────────────────────────────────────────────
    # If explicit file paths are given, use them directly (backward compat / smoke test).
    # Otherwise use StorageClient.
    use_files = bool(a.knowledge or a.runtime)
    store = None

    if use_files:
        if not a.knowledge or not a.runtime:
            ap.error("--knowledge and --runtime must both be provided when using file mode")
        knowledge = load(a.knowledge)
        resolved, total_sessions = resolved_runtimes(a.runtime)
        # resolved = list of (conv_id, rt_dict)
    else:
        from storage import StorageClient
        store = StorageClient(source=a.source, env_file=a.env_file)
        conv_ids = store.list_promotable(a.machine_id)
        resolved = []
        for cid in conv_ids:
            try:
                rt = store.get_runtime(a.machine_id, cid)
                if rt.get("status") in RESOLVED_STATUSES:
                    resolved.append((cid, rt))
            except Exception as exc:
                print(f"  [warn] could not fetch runtime {cid}: {exc}")
        total_sessions = len(conv_ids)
        knowledge = store.get_knowledge(a.machine_id)

    machine   = knowledge.get("_meta", {}).get("machine_id", a.machine_id)
    fm_index  = {fm["id"]: fm for fm in knowledge.get("failure_modes", [])}
    skipped_open = total_sessions - len(resolved)

    raw     = [build_change(cid, rt, fm_index, knowledge) for cid, rt in resolved]
    already = sum(1 for c in raw if c is None)
    changes = [c for c in raw if c is not None]

    adds = [c for c in changes if c["op"] == "add"]

    # schema used for the per-draft ADD gate. Defaults to contracts/schema.json
    # even when --schema is not passed, so the ADD merge gate is always real.
    # (The whole-knowledge validation below still only runs with an explicit
    # --schema, preserving the smoke-test path.)
    add_schema = a.schema or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), os.pardir, "contracts", "schema.json")

    # ── header ────────────────────────────────────────────────────────────────
    src_label = "files" if use_files else f"bucket/{a.source}"
    print(f"promote.py — {machine}  ({datetime.date.today().isoformat()})  [{src_label}]")
    print(
        f"sessions: {total_sessions} total · {len(resolved)} resolved · "
        f"{skipped_open} skipped (not resolved) · {already} already promoted"
    )

    # enrich/revise blocks (ADDs are handled in their own section below)
    for i, ch in enumerate(changes, 1):
        if ch["op"] == "add":
            continue
        print_change(ch, i, len(changes))

    # ── ADD path ────────────────────────────────────────────────────────────────
    # dry-run: draft each new FM (LLM) → out/add_<conv>.draft.json, needs authoring.
    # --apply: merge only drafts whose TODOs are filled and that pass schema.
    add_merged, add_blocked, add_drafted = [], [], []
    for ch in adds:
        conv = ch["grounding"]["conversation_id"]
        draft_path = os.path.join(a.out, f"add_{conv}.draft.json")
        print(f"\n── ADD  {conv}")
        print(f"   narrative : {ch['grounding']['narrative']}")
        if a.apply:
            # idempotency: never re-add a conv already folded into a failure_mode
            if any(conv in fm.get("provenance", []) for fm in knowledge.get("failure_modes", [])):
                print("   already promoted — skipping")
                ch["deferred"] = True
                continue
            draft, reason = load_completed_draft(draft_path, add_schema)
            if draft is None:
                print(f"   ADD blocked: {conv} draft incomplete "
                      f"(unfilled TODOs / schema-invalid), not merged")
                print(f"     reason: {reason}")
                ch["deferred"] = True
                add_blocked.append(conv)
            else:
                draft["provenance"] = [conv]
                draft["evidence_count"] = 1
                ch["after"] = draft
                ch["target_id"] = draft.get("id", ch["target_id"])
                ch["deferred"] = False
                print(f"   merge     : new failure_mode {ch['target_id']}  "
                      f"(draft complete ← {draft_path})")
                add_merged.append(conv)
        else:
            path, err = write_add_draft(ch, knowledge, a.out)
            if err:
                print(f"   ADD draft FAILED ({err}) — no draft written, fix and re-run")
            else:
                print(f"   ADD (draft written → {path}, needs human authoring)")
                add_drafted.append(path)

    # ── summary ──────────────────────────────────────────────────────────────────
    counts = {}
    for c in changes:
        if c["op"] != "add":
            counts[c["op"]] = counts.get(c["op"], 0) + 1

    parts = []
    for op in ("enrich", "revise"):
        if op in counts:
            parts.append(f"{counts[op]} {op}")
    if adds:
        if a.apply:
            if add_merged:
                parts.append(f"{len(add_merged)} add (merged)")
            if add_blocked:
                parts.append(f"{len(add_blocked)} add (blocked — incomplete)")
        else:
            parts.append(f"{len(add_drafted)} add (draft written, needs authoring)")
    parts.append(f"{skipped_open + already} skipped")

    print(f"\n{'─' * 60}")
    print("  " + " · ".join(parts))

    # ── apply ─────────────────────────────────────────────────────────────────
    if a.apply:
        os.makedirs(a.out, exist_ok=True)
        candidate = bump_version(apply_changes(knowledge, changes))

        errs = validate_schema(candidate, a.schema) if a.schema else []
        if errs:
            print(f"\nSchema validation FAILED — not writing:")
            for e in errs[:5]:
                print(f"  {e}")
            sys.exit(1)

        new_version = candidate["_meta"]["version"]

        # recompute after ADD gating: merged ADDs flipped to deferred=False above
        active   = [c for c in changes if not c.get("deferred")]
        deferred = [c for c in changes if c.get("deferred")]

        if use_files:
            kb_out = os.path.join(a.out, f"knowledge-{machine}.json")
            with open(kb_out, "w") as f:
                json.dump(candidate, f, indent=2)
        else:
            kb_out = f"storage: knowledge/{machine}.json"
            store.put_knowledge(machine, candidate)

        # reference files for tooling / tests (local only)
        if use_files:
            with open(os.path.join(a.out, "candidate.json"), "w") as f:
                json.dump(candidate, f, indent=2)
            with open(os.path.join(a.out, "changes.json"), "w") as f:
                json.dump(changes, f, indent=2)

        log_out = os.path.join(a.out, f"decision-log-{datetime.date.today().isoformat()}.json")
        log = {
            "machine": machine,
            "at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "parent_version": knowledge.get("_meta", {}).get("version"),
            "new_version": new_version,
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

        # stamp vault ledger for sessions that were actually folded in (ENRICH,
        # REVISE, and merged ADDs alike — `active` already excludes blocked ADDs)
        promoted_ids = [c["grounding"]["conversation_id"] for c in active]
        if promoted_ids:
            print(f"         promoted: {promoted_ids}")
            if store is not None:
                store.mark_promoted(promoted_ids, new_version)

        print(f"\n--apply: wrote {kb_out}  (version {new_version})")
        print(f"         wrote {log_out}")
    else:
        print(f"\n(dry-run — pass --apply to write knowledge.json + decision log)")


if __name__ == "__main__":
    main()
