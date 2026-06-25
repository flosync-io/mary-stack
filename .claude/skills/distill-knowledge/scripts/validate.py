#!/usr/bin/env python3
"""
Validate a knowledge JSON instance against a JSON Schema (Draft 2020-12).

Handles two file shapes:
  1. Collections-of-arrays (the production state): top-level keys map to arrays of
     entities (e.g. {"failure_modes": [...], "checks": [...]}). Validated as a whole
     against the root schema, so every present collection's items are checked.
  2. One-example-per-key (a worked-example contract file): top-level keys are single
     objects (e.g. {"failure_mode": {...}, "check": {...}}). Each is validated against
     a matching entity definition in the schema's "$defs".

It also meta-schema-checks the schema itself, so a malformed schema is caught early.

Usage:
    python validate.py <schema.json> <instance.json> [--map key=defName,...]

  --map  Override how singular example keys map to $defs entries
         (e.g. --map procedure_escalate_example=procedure). Only needed in
         one-example-per-key mode when a key can't be auto-resolved.

Exit code 0 = valid, 1 = errors found (or bad schema / bad args).

Requires: jsonschema >= 4.18  (pip install -U "jsonschema>=4.18" --break-system-packages)
"""
import json
import sys


def load(path):
    with open(path) as f:
        return json.load(f)


def jptr(path):
    return "/" + "/".join(str(p) for p in path) if path else "(root)"


def resolve_def(key, defs, overrides):
    """Find the $def name for a singular example key."""
    if key in overrides:
        return overrides[key]
    if key in defs:
        return key
    # try simple singular/plural and '*_example' fallbacks
    cands = [key.rstrip("s"), key + "s", key.replace("_example", ""),
             key.split("_example")[0]]
    for c in cands:
        if c in defs:
            return c
    return None


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    schema_path, instance_path = argv[0], argv[1]
    overrides = {}
    for a in argv[2:]:
        if a.startswith("--map"):
            spec = a.split("=", 1)[1] if "=" in a else (argv[argv.index(a) + 1])
            for pair in spec.split(","):
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    overrides[k.strip()] = v.strip()

    try:
        from jsonschema import Draft202012Validator
    except Exception:
        print("ERROR: needs jsonschema>=4.18. "
              'Install: pip install -U "jsonschema>=4.18" --break-system-packages')
        return 1

    schema = load(schema_path)
    instance = load(instance_path)

    # 1) meta-schema check
    try:
        Draft202012Validator.check_schema(schema)
        print("schema: valid Draft 2020-12 meta-schema  OK")
    except Exception as e:
        print("schema: INVALID ->", e)
        return 1

    defs = schema.get("$defs", schema.get("definitions", {}))
    has_arrays = isinstance(instance, dict) and any(
        isinstance(v, list) for k, v in instance.items() if not k.startswith("$"))

    total_errors = 0

    if has_arrays:
        # collections-of-arrays mode: validate whole doc against the root schema
        print("mode: collections-of-arrays (validating whole doc against root)")
        v = Draft202012Validator(schema)
        for e in sorted(v.iter_errors(instance), key=lambda e: list(e.path)):
            total_errors += 1
            print(f"  FAIL {jptr(list(e.path))}: {e.message}")
        # report per-collection counts
        for k, val in instance.items():
            if isinstance(val, list):
                print(f"  - {k}: {len(val)} item(s)")
    else:
        # one-example-per-key mode: validate each entity against its $def
        print("mode: one-example-per-key (validating each key against $defs)")
        if not defs:
            print("  ERROR: schema has no $defs to validate singular keys against.")
            return 1
        for key, val in instance.items():
            if key.startswith("$"):
                continue
            d = resolve_def(key, defs, overrides)
            if not d:
                print(f"  SKIP {key}: no matching $def (use --map {key}=<defName>)")
                continue
            sub = {"$ref": f"#/$defs/{d}", "$defs": defs}
            v = Draft202012Validator(sub)
            errs = sorted(v.iter_errors(val), key=lambda e: list(e.path))
            if errs:
                total_errors += len(errs)
                print(f"  FAIL {key} (as {d}): {len(errs)} error(s)")
                for e in errs[:20]:
                    print(f"     {jptr(list(e.path))}: {e.message}")
            else:
                print(f"  OK   {key} (as {d})")

    print()
    if total_errors == 0:
        print("RESULT: VALID — 0 errors")
        return 0
    print(f"RESULT: {total_errors} error(s)")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
