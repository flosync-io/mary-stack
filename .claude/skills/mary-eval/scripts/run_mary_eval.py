#!/usr/bin/env python3
"""
Mary Eval runner.

Runs scripted operator conversations against the Machine Mary Dify app and
writes scored results. Multi-turn scenarios are threaded via Dify's
conversation_id so Mary actually remembers the conversation.

Stdlib only — no pip installs required.

Usage:
    DIFY_API_KEY="app-XXXX" python3 run_mary_eval.py \
        --scenarios scenarios.yaml --out results.json

Env:
    DIFY_API_KEY   required, the Dify *app* API key (format app-...)
    DIFY_BASE_URL  optional, defaults to https://api.dify.ai/v1
"""

import argparse
import concurrent.futures
import json
import os
import re
import sys
import urllib.request
import urllib.error

try:
    from _env import load_env
except Exception:  # noqa: BLE001 — degrade gracefully if run without _env.py
    def load_env(_=None):
        return []


# ----------------------------- tiny YAML loader -----------------------------
# Avoids a PyYAML dependency. Supports the subset used by scenarios.example.yaml:
# top-level "scenarios:" list, scalar keys, inline-list values ([a, b]), and
# block lists of mappings for "turns:". If PyYAML is available, we use it.
def load_scenarios(path):
    try:
        import yaml  # type: ignore
        with open(path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        return data.get("scenarios", []) if isinstance(data, dict) else (data or [])
    except ImportError:
        pass  # fall through to the minimal parser
    with open(path, "r", encoding="utf-8") as fh:
        return _minimal_parse(fh.read())


def _coerce(v):
    v = v.strip()
    if v == "" or v.lower() in ("null", "~"):
        return None
    if v.lower() in ("true", "false"):
        return v.lower() == "true"
    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
        return v[1:-1]
    if v.startswith("[") and v.endswith("]"):
        inner = v[1:-1].strip()
        if not inner:
            return []
        return [_coerce(x) for x in _split_inline_list(inner)]
    try:
        return int(v)
    except ValueError:
        return v


def _split_inline_list(inner):
    out, buf, q = [], "", None
    for ch in inner:
        if q:
            buf += ch
            if ch == q:
                q = None
        elif ch in "\"'":
            q = ch
            buf += ch
        elif ch == ",":
            out.append(buf)
            buf = ""
        else:
            buf += ch
    if buf.strip():
        out.append(buf)
    return out


def _minimal_parse(text):
    """Parse the documented scenarios subset. Indentation = 2 spaces."""
    lines = [ln.rstrip() for ln in text.split("\n")
             if ln.strip() and not ln.strip().startswith("#")]
    # strip a leading "scenarios:" header if present
    if lines and lines[0].strip().rstrip(":") == "scenarios":
        lines = lines[1:]
    scenarios, cur, ctx = [], None, None
    for ln in lines:
        indent = len(ln) - len(ln.lstrip())
        s = ln.strip()
        if indent == 0 and s.startswith("- "):
            cur = {}
            scenarios.append(cur)
            ctx = None
            s = s[2:].strip()
            if ":" in s:
                k, v = s.split(":", 1)
                cur[k.strip()] = _coerce(v)
            continue
        if cur is None:
            continue
        if s.endswith(":") and s[:-1] in ("turns",):
            cur["turns"] = []
            ctx = "turns"
            continue
        if ctx == "turns" and s.startswith("- "):
            item = {}
            cur["turns"].append(item)
            body = s[2:].strip()
            if ":" in body:
                k, v = body.split(":", 1)
                item[k.strip()] = _coerce(v)
            continue
        if ctx == "turns" and cur["turns"] and ":" in s:
            k, v = s.split(":", 1)
            cur["turns"][-1][k.strip()] = _coerce(v)
            continue
        if ":" in s:
            k, v = s.split(":", 1)
            cur[k.strip()] = _coerce(v)
            ctx = None
    return scenarios


# ----------------------------- Dify client ---------------------------------
def call_dify(base_url, api_key, query, inputs, user, conversation_id):
    body = {
        "inputs": inputs,
        "query": query,
        "response_mode": "blocking",
        "user": user,
        "conversation_id": conversation_id or "",
    }
    req = urllib.request.Request(
        base_url.rstrip("/") + "/chat-messages",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + api_key,
            "Content-Type": "application/json",
            # Cloudflare in front of api.dify.ai rejects the default
            # "Python-urllib/x.y" UA with 403 error 1010. Send a normal one.
            "User-Agent": "mary-eval/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ----------------------------- checks --------------------------------------
ALARM_RE = re.compile(r"\b\d{4,6}\b")
VALUE_RE = re.compile(
    r"\b\d+(\.\d+)?\s*(mm|in|inch|ipm|rpm|sfm|mm/min|m/min)\b", re.IGNORECASE)


def parse_answer(answer_text):
    """Mary returns a JSON string in the Dify 'answer' field."""
    try:
        obj = json.loads(answer_text)
        if isinstance(obj, dict):
            return obj, True
    except (ValueError, TypeError):
        pass
    return {"message": answer_text or "", "status": "", "capture": "", "options": []}, False


def run_checks(scenario, trajectory):
    """Deterministic checks over the full trajectory."""
    operator_alarms = set()
    for t in scenario.get("turns", []):
        operator_alarms |= set(ALARM_RE.findall(str(t.get("operator", ""))))

    results = {}
    all_json_ok = all(step["valid_json"] for step in trajectory) if trajectory else False
    results["valid_json"] = all_json_ok

    # no fabricated alarm numbers in Mary's messages
    fabricated = []
    for step in trajectory:
        for code in ALARM_RE.findall(step["message"]):
            if code not in operator_alarms:
                fabricated.append({"turn": step["turn"], "code": code})
    results["no_fabricated_alarm"] = (len(fabricated) == 0)
    if fabricated:
        results["_fabricated_alarms"] = fabricated

    # no invented tool/offset/feed/speed values
    values = []
    for step in trajectory:
        for m in VALUE_RE.finditer(step["message"]):
            values.append({"turn": step["turn"], "value": m.group(0)})
    results["no_fabricated_values"] = (len(values) == 0)
    if values:
        results["_values"] = values

    # status never regresses after advancing past the opening
    statuses = [step["status"] for step in trajectory if step["status"]]
    regressed = False
    seen_advanced = False
    for st in statuses:
        if st in ("resolved", "escalated"):
            seen_advanced = True
        elif seen_advanced and st == "diagnosing":
            regressed = True
    results["status_progression"] = not regressed

    # flags honored: if any turn sent confirmed/closeout, status should advance by the end
    sent_closeout = any(
        isinstance(t.get("flags"), str) and ('"closeout": true' in t["flags"] or '"confirmed": true' in t["flags"])
        for t in scenario.get("turns", [])
    )
    if sent_closeout:
        last_status = statuses[-1] if statuses else ""
        results["flags_honored"] = last_status in ("resolved", "escalated")
    # expected_status assertion
    exp = scenario.get("expected_status")
    if exp:
        last_status = statuses[-1] if statuses else ""
        results["expected_status"] = (last_status == exp)
        results["_final_status"] = last_status

    # must_mention / must_not_mention over concatenated Mary messages
    blob = " ".join(step["message"].lower() for step in trajectory)
    for needle in scenario.get("must_mention", []) or []:
        results.setdefault("must_mention", {})[needle] = (str(needle).lower() in blob)
    for needle in scenario.get("must_not_mention", []) or []:
        results.setdefault("must_not_mention", {})[needle] = (str(needle).lower() not in blob)

    return results


# ----------------------------- scenario runner -----------------------------
def run_scenario(base_url, api_key, scenario):
    name = scenario.get("name", "unnamed")
    operator_id = str(scenario.get("operator_id", "op-test"))
    machine_id = str(scenario.get("machine_id", "unknown"))
    user = operator_id
    conversation_id = ""
    trajectory = []
    error = None

    try:
        for i, turn in enumerate(scenario.get("turns", []), start=1):
            query = str(turn.get("operator", ""))
            flags = turn.get("flags")
            flags = flags if isinstance(flags, str) else "{}"
            inputs = {"operator_id": operator_id, "machine_id": machine_id, "flags": flags}
            resp = call_dify(base_url, api_key, query, inputs, user, conversation_id)
            conversation_id = resp.get("conversation_id", conversation_id)
            answer = resp.get("answer", "")
            parsed, ok = parse_answer(answer)
            trajectory.append({
                "turn": i,
                "operator": query,
                "flags": flags,
                "message": str(parsed.get("message", "")),
                "status": str(parsed.get("status", "")),
                "capture": str(parsed.get("capture", "")),
                "options": parsed.get("options", []),
                "valid_json": ok,
                "raw": answer,
            })
    except urllib.error.HTTPError as e:
        error = "HTTP %s: %s" % (e.code, e.read().decode("utf-8", "ignore")[:500])
    except Exception as e:  # noqa: BLE001
        error = "%s: %s" % (type(e).__name__, e)

    checks = run_checks(scenario, trajectory) if trajectory else {}
    return {
        "name": name,
        "operator_id": operator_id,
        "machine_id": machine_id,
        "rubric": scenario.get("rubric", ""),
        "turns_run": len(trajectory),
        "trajectory": trajectory,
        "checks": checks,
        "error": error,
    }


def write_trajectories_md(results, path):
    lines = ["# Mary eval trajectories\n"]
    for r in results:
        lines.append("## %s  (machine: %s, operator: %s)\n" % (r["name"], r["machine_id"], r["operator_id"]))
        if r["rubric"]:
            lines.append("**Rubric:** %s\n" % r["rubric"])
        if r["error"]:
            lines.append("> RUN ERROR: %s\n" % r["error"])
        for step in r["trajectory"]:
            lines.append("**Turn %d — operator:** %s" % (step["turn"], step["operator"]))
            if step["flags"] and step["flags"] != "{}":
                lines.append("  _(flags: %s)_" % step["flags"])
            lines.append("**Mary [%s]:** %s\n" % (step["status"] or "?", step["message"]))
        lines.append("**Checks:** `%s`\n" % json.dumps(r["checks"]))
        lines.append("\n---\n")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))


def main():
    ap = argparse.ArgumentParser(description="Run Mary eval scenarios against Dify.")
    ap.add_argument("--scenarios", required=True, help="path to scenarios.yaml")
    ap.add_argument("--out", default="results.json", help="path for results JSON")
    ap.add_argument("--concurrency", type=int, default=4, help="parallel scenarios")
    ap.add_argument("--env-file", default=None, help="path to a .env file with DIFY_API_KEY")
    args = ap.parse_args()

    load_env(args.env_file)
    api_key = os.environ.get("DIFY_API_KEY", "").strip()
    base_url = os.environ.get("DIFY_BASE_URL", "https://api.dify.ai/v1").strip()
    if not api_key:
        sys.exit("ERROR: set DIFY_API_KEY (the Dify app API key, format app-...).")

    scenarios = load_scenarios(args.scenarios)
    if not scenarios:
        sys.exit("ERROR: no scenarios found in %s" % args.scenarios)

    results = [None] * len(scenarios)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as ex:
        futs = {ex.submit(run_scenario, base_url, api_key, sc): idx
                for idx, sc in enumerate(scenarios)}
        for fut in concurrent.futures.as_completed(futs):
            results[futs[fut]] = fut.result()

    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump({"scenarios": results}, fh, indent=2)
    md_path = os.path.splitext(args.out)[0].replace("results", "trajectories") + ".md"
    if md_path == args.out:
        md_path = args.out + ".trajectories.md"
    write_trajectories_md(results, md_path)

    # console summary
    n = len(results)
    errored = sum(1 for r in results if r["error"])
    print("Ran %d scenario(s); %d errored." % (n, errored))
    for r in results:
        flat = []
        for k, v in r["checks"].items():
            if k.startswith("_"):
                continue
            if isinstance(v, bool):
                flat.append("%s=%s" % (k, "OK" if v else "FAIL"))
        status = "ERROR(%s)" % r["error"] if r["error"] else ", ".join(flat)
        print("  - %-28s %s" % (r["name"], status))
    print("Wrote %s and %s" % (args.out, md_path))


if __name__ == "__main__":
    main()
