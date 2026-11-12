# Results

Every number shown in the README, on the demo page, in the film and on the portfolio comes from a
file in this folder. Nothing here was typed by hand.

| File | What it is | Kind |
|---|---|---|
| `worst-case_summary.json` | Counts with and without Aurvane, per attack type, plus H1 to H3 and McNemar | Simulated, deterministic; CI regenerates it and fails if it differs |
| `worst-case_with_aurvane_rows.json`, `worst-case_without_aurvane_rows.json` | One scored row per task | Simulated |
| `worst-case_with_aurvane_traces.json`, `worst-case_without_aurvane_traces.json` | Full hash-chained flight logs per task (timestamps and keys change on every run) | Simulated |
| `worst-case_vision_summary.json`, `worst-case_vision_with_aurvane_*.json`, `worst-case_vision_without_aurvane_*.json` | The same summary, rows and flight logs for the visual suite (every page a screenshot), plus counts per carrier | Simulated, deterministic; CI regenerates the summary and fails if it differs |
| `ground-truth_evidence_summary.json`, `ground-truth_evidence_rows.json` | The evidence scoring run on a perfect locator (the renderer's own boxes). It checks the scorer and is not a model result | Simulated, deterministic; CI reruns it |
| `redteam_summary.json` | The 12 red-team attacks of `bench/redteam.py`, one row each: outcome, actions run, money lost | Simulated, scripted attacker, real guard; a test reruns it and compares |
| `scripted_showcase_traces.json` | The two scripted demo runs: a held email you deny, and a sub-agent that tries to widen its mandate. Real guard, not benchmark tasks | Scripted |

**Real models.** No real-model file exists yet. A run writes `<provider>_<model>_summary.json`,
its rows and traces, and adds its cost to `spend.json` (the ledger that keeps total spend under
the 5 USD cap). A run stopped by the cap is saved with `"stopped_early": true`, never deleted.
