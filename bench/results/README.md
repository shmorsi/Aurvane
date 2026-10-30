# Results

Every number shown in the README, on the demo page, in the film and on the portfolio comes from a
file in this folder. Nothing here was typed by hand.

| File | What it is | Kind |
|---|---|---|
| `worst-case_summary.json` | Counts with and without Aurvane, per attack type, plus H1 to H3 and McNemar | Simulated, deterministic; CI regenerates it and fails if it differs |
| `worst-case_with_aurvane_rows.json`, `worst-case_without_aurvane_rows.json` | One scored row per task | Simulated |
| `worst-case_with_aurvane_traces.json`, `worst-case_without_aurvane_traces.json` | Full hash-chained flight logs per task (timestamps and keys change on every run) | Simulated |
| `scripted_showcase_traces.json` | The two scripted demo runs: a held email you deny, and a sub-agent that tries to widen its mandate. Real guard, not benchmark tasks | Scripted |

**Real models.** No real-model file exists yet. A run writes `<provider>_<model>_summary.json`,
its rows and traces, and adds its cost to `spend.json` (the ledger that keeps total spend under
the 5 USD cap). A run stopped by the cap is saved with `"stopped_early": true`, never deleted.
