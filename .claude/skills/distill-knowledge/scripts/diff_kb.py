#!/usr/bin/env python3
"""
Structural diff of two knowledge JSONs that share a collections-of-arrays shape
and an `id` key per entity. Reports, per collection:
  - item counts (old vs new)
  - ids ADDED (in new, not old) and REMOVED (in old, not new)
  - ids CHANGED (present in both, but some top-level field differs), with the
    changed field names

This is a structural/identity diff, not a semantic one: it tells you what moved,
not whether the move was correct. Use it as the factual backbone of a distillation
diff report, then add the judgement calls (recovered/missed concepts, grounding,
conflicts) on top.

Usage:
    python diff_kb.py <old.json> <new.json> [--collections a,b,c] [--id-key id] [--json]

  --collections  Restrict to these top-level collections (default: every list-valued
                 key present in either file).
  --id-key       The identity field (default: "id").
  --json         Emit machine-readable JSON instead of the text report.
"""
import json
import sys


def load(path):
    with open(path) as f:
        return json.load(f)


def list_collections(d):
    return {k for k, v in d.items() if isinstance(v, list)}


def index_by_id(items, id_key):
    out = {}
    for i, it in enumerate(items):
        if isinstance(it, dict) and id_key in it:
            out[it[id_key]] = it
        else:
            out[f"<no-id #{i}>"] = it
    return out


def changed_fields(a, b):
    """Top-level fields whose values differ between two entity dicts."""
    if not (isinstance(a, dict) and isinstance(b, dict)):
        return ["<non-object>"] if a != b else []
    fields = []
    for k in sorted(set(a) | set(b)):
        if k.startswith("$"):
            continue
        if a.get(k) != b.get(k):
            fields.append(k)
    return fields


def diff(old, new, collections=None, id_key="id"):
    cols = collections or sorted(list_collections(old) | list_collections(new))
    report = {}
    for c in cols:
        oi = index_by_id(old.get(c, []) or [], id_key)
        ni = index_by_id(new.get(c, []) or [], id_key)
        added = sorted(set(ni) - set(oi))
        removed = sorted(set(oi) - set(ni))
        changed = {}
        for i in sorted(set(oi) & set(ni)):
            cf = changed_fields(oi[i], ni[i])
            if cf:
                changed[i] = cf
        report[c] = {
            "count_old": len(oi),
            "count_new": len(ni),
            "added": added,
            "removed": removed,
            "changed": changed,
        }
    return report


def text_report(report):
    lines = []
    lines.append("# Knowledge JSON diff\n")
    lines.append("| collection | old | new | +added | -removed | ~changed |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for c, r in report.items():
        lines.append(f"| {c} | {r['count_old']} | {r['count_new']} | "
                     f"{len(r['added'])} | {len(r['removed'])} | {len(r['changed'])} |")
    lines.append("")
    for c, r in report.items():
        if not (r["added"] or r["removed"] or r["changed"]):
            continue
        lines.append(f"## {c}")
        if r["added"]:
            lines.append(f"- **added** ({len(r['added'])}): {', '.join(r['added'])}")
        if r["removed"]:
            lines.append(f"- **removed** ({len(r['removed'])}): {', '.join(r['removed'])}")
        for i, fields in r["changed"].items():
            lines.append(f"- **changed** `{i}`: {', '.join(fields)}")
        lines.append("")
    return "\n".join(lines)


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    old_path, new_path = argv[0], argv[1]
    collections = None
    id_key = "id"
    as_json = False
    i = 2
    while i < len(argv):
        a = argv[i]
        if a == "--collections":
            collections = [x.strip() for x in argv[i + 1].split(",")]
            i += 2
        elif a == "--id-key":
            id_key = argv[i + 1]
            i += 2
        elif a == "--json":
            as_json = True
            i += 1
        else:
            i += 1
    report = diff(load(old_path), load(new_path), collections, id_key)
    if as_json:
        print(json.dumps(report, indent=2))
    else:
        print(text_report(report))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
