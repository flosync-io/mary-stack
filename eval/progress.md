# eval — progress

## Now
- WS3 variant & evolution on pp/dev/ws3-variant-evolution: phrasing variants + harder evolutions for tests #10, #11, #44.
- DMC80FD-01 happy path baseline established (B-mode, 4/4, conv 949705bb). No failing cases found yet on this machine.
- Unknown-fault sweep done (10 scenarios, B-mode) — see notes.md. Abstention is honest-and-quick; escape/decline confirmed live. Surfaced 3 build items (floor, #7 empty handoff capture, #9 terminal regression) + A7 unbuilt.

## Next
- Promote unknown-fault findings to scripted A-mode so they can't regress: the #7 empty-capture and #9 terminal-regression cases especially.
- Generate 5 paraphrases per test, freeze ≤3 after human review, score with parent rubric.

## Open questions
- (none logged yet)
