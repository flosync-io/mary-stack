#!/usr/bin/env python3
"""
Engine integration tests — run against the CURRENT machine-mary-imd-chatflow.yml.

No credentials needed. Extracts the guard + engine + envelope Code nodes from the
DSL and drives full conversations, asserting moves / status / trace / envelope.
This is the regression gate: run it after every yml change.

    python3 tests/test_engine.py
Exits non-zero if any scenario fails.
"""
import os, json, tempfile, importlib.util, sys
import yaml

YML = os.path.join(os.path.dirname(__file__), "..", "machine-mary-imd-chatflow.yml")


def load_engine():
    d = yaml.safe_load(open(YML))
    byid = {n["id"]: n for n in d["workflow"]["graph"]["nodes"]}
    guard = byid["guard"]["data"]["code"].replace("def main(", "def guard_main(")
    engine = byid["engine"]["data"]["code"].replace("def main(", "def engine_main(")
    env = byid["envelope"]["data"]["code"].replace("def main(", "def envelope_main(")
    src = guard + "\n\n" + engine + "\n\n" + env
    f = tempfile.NamedTemporaryFile("w", suffix=".py", delete=False); f.write(src); f.close()
    spec = importlib.util.spec_from_file_location("mary_engine", f.name)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); os.unlink(f.name)
    KJ = next(e["value"] for e in d["workflow"]["environment_variables"] if e["name"] == "knowledge_json")
    return m, KJ


class Session:
    def __init__(self, m, KJ):
        self.m, self.KJ = m, KJ
        self.cv = {"stage": "INTAKE", "case": "{}", "matched_fm": "", "candidate_causes": "[]",
                   "ruled_out": "[]", "current_cause": "", "current_check": "",
                   "current_step_idx": 0, "attempts": 0, "clarify_attempts": 0}

    def turn(self, kind, value, scores=None, flags="{}"):
        sig = {"kind": kind, "text": value, "value": value}
        g = self.m.guard_main(sig, self.KJ)
        r = self.m.engine_main(sig, scores or {"scores": []}, g["guard_decision"], g["guard_reason"], self.KJ,
                               self.cv["stage"], self.cv["case"], self.cv["matched_fm"], self.cv["candidate_causes"],
                               self.cv["ruled_out"], self.cv["current_cause"], self.cv["current_check"],
                               self.cv["current_step_idx"], self.cv["attempts"], 4, flags, self.cv["clarify_attempts"])
        for k in ["stage", "case", "matched_fm", "candidate_causes", "ruled_out",
                  "current_cause", "current_check", "current_step_idx", "attempts", "clarify_attempts"]:
            self.cv[k] = r["out_" + k]
        env = self.m.envelope_main(r["render_brief"], r["out_status"], r["out_options"], r["out_capture"], r["out_trace"], r["allowed_facts"], r["out_modality"], r["out_default"])
        return {"move": r["move_type"], "status": r["out_status"], "terminal": r["terminal"],
                "trace": json.loads(r["out_trace"]), "envelope": json.loads(env["envelope"]),
                "case": json.loads(self.cv["case"])}


# ---------------- scenarios ----------------
TESTS = []
def test(fn): TESTS.append(fn); return fn

@test
def sanity_is_first_beat(m, KJ):
    s = Session(m, KJ)
    r = s.turn("symptom", "program halted at cycle start, alarm 10620")
    assert r["move"] == "SANITY", r["move"]
    assert r["status"] == "sanity", r["status"]

@test
def green_cycle_start_limit(m, KJ):
    s = Session(m, KJ)
    s.turn("symptom", "cycle start halt, alarm 10620")
    s.turn("check_answer", "nothing changed")
    s.turn("check_answer", "10620 software limit")      # routes wrong_work_offset
    s.turn("confirmation", "done")
    s.turn("confirmation", "done")
    r = s.turn("confirmation", "yep G54 matches and it runs clean")
    assert r["move"] == "RESOLVED", r["move"]
    assert r["case"]["status"] == "resolved", r["case"]["status"]

@test
def green_coolant_via_scores(m, KJ):
    s = Session(m, KJ)
    s.turn("symptom", "bad finish, tools dying, no alarm")
    s.turn("check_answer", "nothing changed", scores={"scores": [{"fm_id": "fm_coolant_concentration_low", "score": 0.85}]})
    s.turn("check_answer", "smells off, tramp oil, refractometer below band too low")
    for _ in range(4):
        r = s.turn("confirmation", "done")
        if r["terminal"] == "true":
            break
    if r["terminal"] != "true":
        r = s.turn("confirmation", "yep within band and finish clean")
    assert r["case"]["status"] == "resolved", r

@test
def safety_bait_stops_then_escalates(m, KJ):
    s = Session(m, KJ)
    s.turn("symptom", "machine threw a 27021 safe stop")
    s.turn("check_answer", "nothing changed")
    bait = s.turn("safety_question", "can I just acknowledge it and keep running?")
    assert bait["move"] == "STOP", bait["move"]
    esc = s.turn("check_answer", "27021 safe stop")
    assert esc["move"] == "ESCALATE", esc["move"]
    assert esc["case"]["status"] == "unresolved", esc["case"]["status"]

@test
def bait_phrase_is_refused(m, KJ):
    s = Session(m, KJ)
    r = s.turn("symptom", "I'll just reset and re-run to clear it")
    assert r["move"] == "STOP", r["move"]

@test
def ambiguous_verify_reasks_not_escalates(m, KJ):
    s = Session(m, KJ)
    s.turn("symptom", "cycle start halt, alarm 10620")
    s.turn("check_answer", "nothing changed")
    s.turn("check_answer", "10620 software limit")
    s.turn("confirmation", "done")
    s.turn("confirmation", "done")             # -> verify question
    r = s.turn("check_answer", "maybe, hard to tell")   # genuinely ambiguous (no yes/no words)
    assert r["move"] == "ASK_CHECK" and r["status"] == "verifying", (r["move"], r["status"])

@test
def closeout_then_confirm_is_green(m, KJ):
    s = Session(m, KJ)
    co = s.turn("closeout_info", "I swapped the insert and the chatter cleared")
    assert co["move"] == "CLOSEOUT", co["move"]
    r = s.turn("confirmation", "confirm, save it")
    assert r["move"] == "RESOLVED" and r["case"]["status"] == "resolved", r

@test
def closeout_does_not_loop_on_sticky_flag(m, KJ):
    # operator returns with the fix -> scribe
    s = Session(m, KJ)
    co = s.turn("closeout_info", "swapped the insert and it cleared")
    assert co["move"] == "CLOSEOUT", co["move"]
    # confirm turn still carries the sticky {closeout} flag (mimics the frontend) -> must resolve, not re-scribe
    r = s.turn("closeout_info", "yes", flags='{"closeout": true}')
    assert r["move"] == "RESOLVED" and r["case"]["status"] == "resolved", ("sticky closeout must resolve", r["move"], r["case"].get("status"))

@test
def confirmed_flag_closes_verify(m, KJ):
    s = Session(m, KJ)
    s.turn("symptom", "cycle start halt, alarm 10620")
    s.turn("check_answer", "nothing changed")
    s.turn("check_answer", "10620 software limit")
    s.turn("confirmation", "done")
    s.turn("confirmation", "done")
    r = s.turn("confirmation", "ran a pass", flags='{"confirmed": true}')
    assert r["move"] == "RESOLVED", r["move"]

@test
def out_of_scope_midflow_advances(m, KJ):
    s = Session(m, KJ)
    s.turn("symptom", "cycle start halt, alarm 10620")
    s.turn("check_answer", "nothing changed")
    s.turn("check_answer", "10620 software limit")        # -> GIVE_STEP
    r = s.turn("out_of_scope", "done")                    # must NOT redirect mid-flow
    assert r["move"] in ("GIVE_STEP", "ASK_CHECK"), r["move"]

@test
def envelope_always_valid_with_trace(m, KJ):
    s = Session(m, KJ)
    for kind, val in [("symptom", "cycle start halt 10620"), ("check_answer", "nothing changed"),
                      ("check_answer", "10620 software limit")]:
        r = s.turn(kind, val)
        env = r["envelope"]
        for key in ("message", "status", "options", "capture", "_trace"):
            assert key in env, "missing %s in envelope" % key
        assert isinstance(env["options"], list)

@test
def render_modality_per_move(m, KJ):
    s = Session(m, KJ)
    r = s.turn("symptom", "cycle start halt, alarm 10620")   # SANITY
    assert r["envelope"]["modality"] == "yes_no" and r["envelope"].get("default") == "No", ("sanity yes/no default No", r["envelope"])
    r = s.turn("check_answer", "nothing changed")            # -> first diagnose check
    assert r["envelope"]["modality"] == "mcq" and len(r["envelope"]["options"]) >= 2, ("check should be mcq w/ taps", r["envelope"])

@test
def ask_clarify_then_resolve_and_cap(m, KJ):
    sc = {"scores": [{"fm_id": "fm_coolant_concentration_low", "score": 0.82}, {"fm_id": "fm_wrong_tool_data", "score": 0.80}]}
    # bunched -> ASK_CLARIFY with >=2 options
    s = Session(m, KJ); s.turn("symptom", "weird symptom no alarm")
    r = s.turn("check_answer", "nothing changed", scores=sc)
    assert r["move"] == "ASK_CLARIFY" and len(r["envelope"]["options"]) >= 2, (r["move"], r["envelope"]["options"])
    # operator picks one option -> matched -> advances to a check
    r2 = s.turn("check_answer", r["envelope"]["options"][0])
    assert r2["move"] == "ASK_CHECK", ("clarify pick should match + advance", r2["move"])
    # cap: an unhelpful answer after the first clarify -> DECLINE (no loop)
    s2 = Session(m, KJ); s2.turn("symptom", "weird symptom no alarm")
    s2.turn("check_answer", "nothing changed", scores=sc)          # clarify #1
    r3 = s2.turn("check_answer", "i really don't know", scores=sc)  # unresolved -> cap -> decline
    assert r3["move"] == "DECLINE", ("cap should decline", r3["move"])

@test
def fact_gate_blocks_ungrounded_numbers(m, KJ):
    import json
    af = json.dumps({"ask": "Compare the active G54 against the traveler"})
    # a number NOT in allowed_facts -> blocked (fallback message)
    e = json.loads(m.envelope_main("Set the offset to -12.4 and rerun.", "resolving", "[]", "", "", af)["envelope"])
    assert "-12.4" not in e["message"], ("ungrounded number should be blocked", e["message"])
    # a value present in allowed_facts (G54) -> passes through
    e = json.loads(m.envelope_main("Check the active G54 part zero.", "diagnosing", "[]", "", "", af)["envelope"])
    assert "G54" in e["message"], ("grounded value should pass", e["message"])
    # incidental small numbers -> not treated as machine values
    e = json.loads(m.envelope_main("Re-home all 3 axes, takes about 10 minutes.", "resolving", "[]", "", "", af)["envelope"])
    assert "3 axes" in e["message"], ("incidental numbers should pass", e["message"])

@test
def relative_floor_decision(m, KJ):
    # clear leader, high -> MATCH (advances to a diagnose check)
    s = Session(m, KJ); s.turn("symptom", "bad finish, tools dying, no alarm")
    r = s.turn("check_answer", "nothing changed", scores={"scores": [{"fm_id": "fm_coolant_concentration_low", "score": 0.85}]})
    assert r["move"] == "ASK_CHECK", ("high-clear should match", r["move"])
    # clear leader but below floor (not bunched) -> DECLINE
    s = Session(m, KJ); s.turn("symptom", "vague thing no alarm")
    r = s.turn("check_answer", "nothing changed", scores={"scores": [{"fm_id": "fm_coolant_concentration_low", "score": 0.30}]})
    assert r["move"] == "DECLINE" and r["trace"].get("reason") == "no_match_below_floor", ("low-clear should decline", r["move"], r["trace"].get("reason"))
    # bunched near-tie -> clarify zone (DECLINE w/ bunched reason until #1)
    s = Session(m, KJ); s.turn("symptom", "weird symptom no alarm")
    r = s.turn("check_answer", "nothing changed", scores={"scores": [{"fm_id": "fm_coolant_concentration_low", "score": 0.82}, {"fm_id": "fm_wrong_tool_data", "score": 0.80}]})
    assert r["move"] == "ASK_CLARIFY", ("bunched should clarify", r["move"], r["trace"].get("reason"))

@test
def status_never_regresses_to_diagnosing(m, KJ):
    s = Session(m, KJ)
    seq = [("symptom", "cycle start halt 10620"), ("check_answer", "nothing changed"),
           ("check_answer", "10620 software limit"), ("confirmation", "done"),
           ("confirmation", "done"), ("confirmation", "yep matches")]
    statuses, advanced = [], False
    for k, v in seq:
        st = s.turn(k, v)["status"]; statuses.append(st)
        if st in ("resolved", "escalated"):
            advanced = True
        assert not (advanced and st == "diagnosing"), statuses


@test
def other_kind_does_not_poison_reported(m, KJ):
    s = Session(m, KJ)
    r = s.turn("other", "hi")
    assert r["move"] == "INTAKE", ("greeting should re-prompt, not SANITY", r["move"])
    assert not r["case"].get("reported"), ("reported must stay empty after greeting", r["case"].get("reported"))
    # second turn: real symptom
    r2 = s.turn("symptom", "coolant smells off and finish has degraded")
    assert r2["move"] == "SANITY", ("real symptom should trigger SANITY", r2["move"])
    assert r2["case"].get("reported"), ("reported must be set after real symptom", r2["case"].get("reported"))


@test
def other_mid_flow_reasks_does_not_advance(m, KJ):
    s = Session(m, KJ)
    # drive to VERIFY (2 resolve steps then verify question)
    s.turn("symptom", "cycle start halt, alarm 10620")
    s.turn("check_answer", "nothing changed")
    s.turn("check_answer", "10620 software limit")  # cause matched -> RESOLVE step 1
    s.turn("confirmation", "done")                  # step 2
    s.turn("confirmation", "done")                  # -> VERIFY question
    # now in VERIFY — send unintelligible input
    r = s.turn("other", "hmm not sure what you mean")
    assert r["move"] == "ASK_CHECK", ("other at VERIFY must re-ask, not advance", r["move"])
    assert r["case"].get("status") != "resolved", ("other must not resolve the case", r["case"].get("status"))
    assert s.cv["stage"] == "VERIFY", ("stage must remain VERIFY", s.cv["stage"])
    # a real positive confirmation now should close it
    r2 = s.turn("confirmation", "yep G54 matches and it runs clean")
    assert r2["move"] == "RESOLVED", r2["move"]


@test
def clarify_none_of_these_drives_decline(m, KJ):
    # bunched scores -> CLARIFY; the engine must append a deterministic escape option,
    # and selecting it must BURN a clarify slot and reach DECLINE at the cap.
    # Regression: rejections used to classify as other (re-ask, no burn) or symptom
    # (back to SANITY, no burn) — DECLINE was unreachable and the cap never tripped.
    sc = {"scores": [{"fm_id": "fm_coolant_concentration_low", "score": 0.82},
                     {"fm_id": "fm_wrong_tool_data", "score": 0.80}]}
    s = Session(m, KJ)
    s.turn("symptom", "weird symptom no alarm")
    r = s.turn("check_answer", "nothing changed", scores=sc)
    assert r["move"] == "ASK_CLARIFY", ("bunched -> clarify", r["move"])
    # escape option is always present, always the same value, always last
    opts = r["envelope"]["options"]
    assert "__none_of_these__" in opts, ("missing none-of-these escape", opts)
    assert opts[-1] == "__none_of_these__", ("escape must be appended last", opts)
    assert opts[0] != "__none_of_these__", ("real candidates must precede the escape", opts)
    entry_attempts = s.cv["clarify_attempts"]

    # operator rejects every candidate. Realistically Interpret tags a button token 'other'
    # (not a described symptom) — exactly the path that used to deadlock.
    moves, attempts = [], []
    last = r
    for _ in range(6):
        last = s.turn("other", "__none_of_these__")
        moves.append(last["move"]); attempts.append(s.cv["clarify_attempts"])
        if last["terminal"] == "true":
            break
    # each rejection burned a slot (strictly increasing) and progressed toward the cap
    assert attempts[0] > entry_attempts, ("none-of-these must burn a clarify slot", entry_attempts, attempts)
    assert all(b > a for a, b in zip([entry_attempts] + attempts, attempts)), ("must increment each turn", attempts)
    # terminates in DECLINE — not a clarify loop, not a SANITY bounce
    assert last["move"] == "DECLINE", ("none-of-these at cap must DECLINE, not loop", moves)
    assert last["terminal"] == "true", ("DECLINE must be terminal", last["terminal"])
    assert last["case"]["status"] == "unresolved", ("DECLINE status must be unresolved", last["case"].get("status"))
    assert "SANITY" not in moves, ("rejection must not bounce to SANITY", moves)
    assert moves[-1] != "ASK_CLARIFY", ("must not end on another clarify re-ask", moves)


def main():
    m, KJ = load_engine()
    fails = 0
    for fn in TESTS:
        try:
            fn(m, KJ); print("PASS", fn.__name__)
        except AssertionError as e:
            fails += 1; print("FAIL", fn.__name__, "->", e)
        except Exception as e:  # noqa: BLE001
            fails += 1; print("ERROR", fn.__name__, "->", type(e).__name__, e)
    print("\n%d/%d passed" % (len(TESTS) - fails, len(TESTS)))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
