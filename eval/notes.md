# eval — notes (rationale & how-things-work)

Detail loaded on demand, not at session start. Promote the *why* here; keep CLAUDE.md to one-liners.

## Decisions

## How things work

**DMC80FD-01 coolant happy path baseline (2026-06-26, B-mode):** Live simulation of "coolant looks off" → `fm_coolant_concentration_low`, cause `cause_coolant_low_concentration`, `proc_check_correct_coolant_concentration`. 8 turns, 4/4 (converged, efficient, safe, faithful). Status progressed `sanity→diagnosing→resolving→verifying→resolved`. Confirmed live `capture` string is `"resolved via proc_check_correct_coolant_concentration; cause cause_coolant_low_concentration"` — exact match to `vault_fields` reconstruction logic. Machine settled on cause in one discriminating check (tramp oil / rust films).
