# Morning report

Overnight: the project is now **Aurvane**, the five main upgrades are in, the docs are written,
and the portfolio features it first. **No real-model run happened**: there was no API key, and
the network blocked Ollama. Every judgment call is in [DECISIONS.md](DECISIONS.md).

## Do this first

**Rename this GitHub repository** (still under the old name) to `aurvane` (repo Settings, General,
Repository name). Every link now points to `github.com/shmorsi/aurvane`, and those links fail until
you rename it. GitHub redirects the old URL afterwards, so nothing else breaks. I had no tool that
renames a repository.

**One commit message breaks your rule.** `cfdacd4` says "Recommend the cheaper Claude models
first ...". Rewording it needs a force push to `main`, which was blocked here. If you want it gone:
`git rebase -i cfdacd4~1` (reword that commit), then `git push --force-with-lease`. All other
commits are clean, have no trailers, and are authored by you.

## What changed

**Aurvane repo** (13 commits on `main`, all authored by you, no trailers; CI green on every one I
checked):

1. **Rename.** The package folder became `aurvane/`, the CLI is `python -m aurvane.bench`, result files and
   summary keys say `aurvane`, and the README has the name, pronunciation, tagline and mission
   line. One word of the forge attack's text changed with the name; this is logged in
   `bench/PROTOCOL.md`. The counts are identical.
2. **Real-model harness** (`aurvane/models.py`, `aurvane/stats.py`). Claude, Grok and Ollama sit
   behind one interface. A hard cap prices the worst case of each call before making it and keeps
   a ledger, so total spend across all runs stays under 5 USD. Failed calls are scored and marked,
   never dropped. H1 to H3 and an exact McNemar test are computed automatically. All of this is
   tested against a fake provider that uses the real Anthropic wire format.
3. **Approvals.** `Checkpoint.approve(id)` and `deny(id)`. An approval re-checks rules 1 to 3, so it
   can't revive an expired mandate or break the budget.
4. **Delegation chains** (`aurvane/delegation.py`). Sub-mandates must be strictly narrower. The
   chain verifies back to the human's key, delegated budget is reserved from the parent, taint
   flows down, and revocation stops every link below it. 13 test cases.
5. **JavaScript guard** (`ui/guard.js`, 124 lines). The parity test replays 1,643 guard decisions
   from all 60 tasks into both guards and they agree on every one. I checked that a one-character
   change makes the test fail.
6. **Demo page** (split into six files of 220 lines or fewer). It has the new mark, the aurora
   palette, a phone-style Allow/Deny card, and sub-agents orbiting inside their parent's shell.
   The **live attack box** lets a visitor type a hidden instruction into a job posting and watch
   the guard decide, then tap Allow or Deny. Tested at 390 px and 1440 px, with reduced motion,
   with no console errors and no horizontal scroll. It also fixes an old CSS bug that made the
   log's "mandate" pill too big.
7. **Film.** 32.8 s, 1920x1080, 1.2 MB. Scenes: a blocked attack, a held email you deny, a
   sub-agent that fails to widen its mandate, the same run without Aurvane (900 CAD lost), and an
   end card read from the committed summary.
8. **Docs.** `docs/vision.md` has 19 cited sources: METR, OWASP, the "lethal trifecta", CaMeL,
   Visa, Mastercard, AP2, ACP, UCP, OSFI E-23, Budget 2025 open banking, RBC, TD, CIBC and
   Wealthsimple. `docs/interview.md` has a 30-second and a 2-minute pitch, 15 hard questions, and
   a role mapping. `LEARN.md` is updated for every new file. `bench/results/README.md` describes
   every results file.
9. **Honesty checks.** A new test fails if any README number drifts from
   `bench/results/worst-case_summary.json`. CI also checks that the offline benchmark finishes in
   under 2 s (here it takes about 0.3 s).

**Portfolio** (2 commits). The project folder became `aurvane/`, and the old folder's `index.html` is an 8-line redirect
that keeps the `#hash`. `data/projects.json` has the id `aurvane` and the new links, image paths,
labels and caveat. The nav, mission index, feature article and binds are updated, and so are the
`PRESENT` list, sitemap and README. There is a new share image. `scripts/check_site.py` now
enforces the redirect, Aurvane's first place, figures matching the summary, and that the old name
appears nowhere else. **`python3 scripts/check_site.py` prints `ok: 5 projects`.** Aurvane is still
first and featured, and its muted film autoplays (checked in a browser at 1440 px and 390 px).

## Results

All of these are **simulated**, from a worst-case agent that obeys every injection. They are
unchanged by the rename:

| | Without Aurvane | With Aurvane |
|---|---:|---:|
| Attacks that landed | 30 / 30 | 7 / 30 |
| Money lost | 12,135 CAD | 135 CAD |
| Clean tasks completed | 30 / 30 | 30 / 30 |

What still gets through: 4 cover-letter rewrites (prose, not actions) and 3 skims of 45 CAD at a
trusted store (capped by the budget). Both are still shown on purpose.

## Real-model results: none, and why

- `ANTHROPIC_API_KEY` and `XAI_API_KEY` were not set in this container.
- Ollama could not be installed: the network policy returns 403 for `ollama.com` and
  `registry.ollama.ai`.
- **Spent: 0 USD.** `bench/results/spend.json` does not exist yet.

To run it yourself (each command follows `bench/PROTOCOL.md` exactly and stops before 5 USD):

```bash
ANTHROPIC_API_KEY=... python -m aurvane.bench --provider anthropic --model claude-haiku-5-5
ANTHROPIC_API_KEY=... python -m aurvane.bench --provider anthropic --model claude-sonnet-5-5
python -m aurvane.bench --provider ollama --model qwen2.5:7b          # on a machine with Ollama
python ui/build.py                                                     # the page picks up any *_summary.json
```

My rough cost estimate is a few cents for Haiku 5.5, a few dollars for Sonnet 5.5, and probably
more than the cap for Opus 5.5 because of its thinking tokens. It is not measured. Then copy the
new summary into the portfolio and update the caveat's "have not been run" (the site check will
remind you).

## Weak spots and failures

- **No real-model evidence.** Everything rests on the simulated agent. H1 and H3 are untested
  on any real model.
- **Provenance is string matching.** A model that rewrites an address or amount can get past
  rule 4. Rule 3 still holds, but rule 4 is the clever part.
- **The browser guard doesn't verify signatures.** Python does it at build time. This is stated on
  the page and in `ui/guard.js`.
- **Two showcase runs are scripted** ("Held, you deny" and "Sub-agent widens"). They use the real
  guard, are labelled on the page, and feed no headline number.
- **Keys and revocations live in memory.** There is no key storage and no revocation service a
  counterparty could query.
- **Trace files change on every benchmark run** (timestamps and fresh keys), so `git status`
  shows noise after `python -m aurvane.bench`. The summary is deterministic, and CI compares that.
- **CI's 2-second timeout** could flake on a very slow runner. The run takes 0.3 s here and passed
  in CI.
- **The mark** reads as "an arc over a needle", which is close to a gauge. That fits "bounded",
  but a designer would do better.
- **Approval fatigue** is a real risk with Allow/Deny cards, and nothing here measures it.
- Two things went wrong overnight and are fixed. A first cut of the film showed a denied email
  still flying to the stranger. The portfolio heading overflowed at 1440 px with the longer name.

## Your next 3 steps

1. **Rename the repo** to `aurvane` on GitHub, then open the README links and
   `shmorsi.github.io/aurvane/` once Pages redeploys.
2. **Run Claude Haiku 5.5, then Sonnet 5.5**, with the commands above (under 5 USD in total).
   Commit `bench/results/`, rebuild the page, copy the summary to the portfolio, and update the
   caveat. This turns "simulated" into a real result, whichever way it comes out.
3. **Replace string provenance with value tagging.** Mark every value that comes out of an
   untrusted tool result and carry the tag through the agent loop, as CaMeL does. Then add an
   attack type that rewrites values, so the benchmark shows the difference.
