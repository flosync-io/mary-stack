#!/usr/bin/env python3
"""
Mary single-turn driver — for LIVE simulation.

Sends ONE operator message to the Machine Mary Dify app and prints Mary's
reply plus the conversation_id. Claude calls this once per turn: read the
conversation_id from the output and pass it back with --conversation-id on the
next turn so Mary remembers the conversation. This is what makes a real
multi-turn simulation possible (the MCP connector is stateless and cannot).

Stdlib only.

Usage (turn 1, no conversation yet):
    DIFY_API_KEY="app-XXXX" python3 mary_turn.py \
        --machine-id dmc80fd_001 --operator-id op-test \
        --query "Coolant pressure keeps dropping mid-cycle."

Usage (later turns — pass the conversation_id from the previous output):
    DIFY_API_KEY="app-XXXX" python3 mary_turn.py \
        --machine-id dmc80fd_001 --operator-id op-test \
        --conversation-id "abc-123" \
        --query "Checked the filter, it was packed with chips." \
        --flags '{"confirmed": true}'

Prints a single JSON line: {conversation_id, status, message, capture, options, valid_json, raw}
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.error

try:
    from _env import load_env
except Exception:  # noqa: BLE001 — degrade gracefully if run without _env.py
    def load_env(_=None):
        return []


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


def parse_answer(answer_text):
    try:
        obj = json.loads(answer_text)
        if isinstance(obj, dict):
            return obj, True
    except (ValueError, TypeError):
        pass
    return {"message": answer_text or "", "status": "", "capture": "", "options": []}, False


def main():
    ap = argparse.ArgumentParser(description="One operator turn to Mary (threaded).")
    ap.add_argument("--query", required=True, help="the operator's message this turn")
    ap.add_argument("--machine-id", required=True)
    ap.add_argument("--operator-id", default="op-test")
    ap.add_argument("--conversation-id", default="", help="from the previous turn's output; omit on turn 1")
    ap.add_argument("--flags", default="{}", help="JSON string of session flags")
    ap.add_argument("--env-file", default=None, help="path to a .env file with DIFY_API_KEY")
    args = ap.parse_args()

    load_env(args.env_file)
    api_key = os.environ.get("DIFY_API_KEY", "").strip()
    base_url = os.environ.get("DIFY_BASE_URL", "https://api.dify.ai/v1").strip()
    if not api_key:
        sys.exit("ERROR: set DIFY_API_KEY (the Dify app API key, format app-...).")

    inputs = {
        "operator_id": args.operator_id,
        "machine_id": args.machine_id,
        "flags": args.flags if isinstance(args.flags, str) else "{}",
    }
    try:
        resp = call_dify(base_url, api_key, args.query, inputs, args.operator_id, args.conversation_id)
    except urllib.error.HTTPError as e:
        sys.exit("HTTP %s: %s" % (e.code, e.read().decode("utf-8", "ignore")[:500]))
    except Exception as e:  # noqa: BLE001
        sys.exit("%s: %s" % (type(e).__name__, e))

    parsed, ok = parse_answer(resp.get("answer", ""))
    trace = parsed.get("_trace", {}) if isinstance(parsed.get("_trace"), dict) else {}
    out = {
        "conversation_id": resp.get("conversation_id", args.conversation_id or ""),
        "status": str(parsed.get("status", "")),
        "message": str(parsed.get("message", "")),
        "capture": str(parsed.get("capture", "")),
        "options": parsed.get("options", []),
        # _trace is Mary's routing signal (in_kind, move, match, reason, ...).
        # Surfaced as first-class fields so the conversation can be read/graded
        # without hand-parsing `raw`. `terminal` is the reliable stop signal.
        "trace": trace,
        "terminal": trace.get("terminal", None),
        "valid_json": ok,
        "raw": resp.get("answer", ""),
    }
    print(json.dumps(out))


if __name__ == "__main__":
    main()
