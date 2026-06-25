# eval/ — Block 3 (Alex + scripted suite)

What this block does: talks to the deployed Mary and grades her against `knowledge.json`.
Emits findings (shape in `contracts/finding.example.json`); grows `scenarios.yml` (Key A).

Durable rules (one line each — promoted here by update-memory):
- A-mode (scripted scenarios.yml) is for regression; B-mode (NL role-play) is for discovery.
- Every finding carries `fault_class` (data|logic|prompt) and the run manifest it was found against.

Memory: read ./progress.md and ./notes.md at task start; run update-memory at task end.
