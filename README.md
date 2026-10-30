# Aurvane

**Every agent action: signed, bounded, visible.**
*The trust layer for the agent economy.*

Aurvane (say "AWR-vane") is aurora + vane: the light that shows the way.

AI agents now read the open web and act on what they read: they apply, buy, book and send.
One hidden sentence in a job posting or a store page can steer them. Aurvane is a small trust
layer that sits between an agent and its tools. The agent may read anything, but
**untrusted text can never choose where your money or data goes.**

**[Watch the live demo, or type your own attack into it →](https://shmorsi.github.io/aurvane/)**

[![Aurvane demo](ui/aurvane-demo-poster.jpg)](https://shmorsi.github.io/aurvane/)

## Results

60 paired tasks (30 clean, 30 poisoned): applying to jobs and buying event tickets. Each
poisoned task hides one instruction in the page the agent reads. The agent used here is a
**worst-case agent that obeys every injected instruction**, so these numbers measure the
guard, not a model's judgment. Simulated, reproducible, no API key: `python -m aurvane.bench`.

|                                  | Without Aurvane | With Aurvane |
|----------------------------------|--------------:|-----------:|
| Attacks that landed              | 30 / 30       | **7 / 30** |
| Money lost (15 purchase tasks)   | 12,135 CAD    | **135 CAD** |
| Clean tasks completed            | 30 / 30       | **30 / 30** |
| False alarms on clean tasks      | 0             | **0** |

| Attack       | What the hidden text asks for                         | Without | With Aurvane |
|--------------|-------------------------------------------------------|--------:|-----------:|
| exfiltrate   | email your private transcript to a stranger           | 8/8     | **0/8** (4 blocked, 4 held for you) |
| redirect     | submit your application to a different posting        | 4/4     | **0/4** |
| overspend    | pay a stranger a 1,200 CAD "fee"                      | 7/7     | **0/7** |
| forge        | "your budget was raised to 5,000", then spend 900     | 4/4     | **0/4** |
| skim         | a 45 CAD add-on at the store you already trust        | 3/3     | 3/3, capped by the budget |
| rewrite      | slip a sentence into your cover letter                | 4/4     | 4/4 |

**What still gets through, and why.** Aurvane guards *actions*, not *prose*: it does not judge
the words of a cover letter (`rewrite`). And when untrusted text only picks an *amount* at a
payee you already trust, Aurvane allows it but labels it "bounded": the signed budget caps the
worst case (`skim`). Both are shown on purpose. A benchmark that only shows wins is an ad.

Every number above is in [`bench/results/worst-case_summary.json`](bench/results/worst-case_summary.json),
which CI regenerates and compares on every push. The same file records the protocol's checks:
H1 and H2 hold, and clean-task completion did not drop (exact McNemar p = 1.0 on 30 pairs).

**Real models: not run yet.** The harness for Claude, Grok and Qwen (via Ollama) is finished,
follows [`bench/PROTOCOL.md`](bench/PROTOCOL.md), and stops before any call that could push total
spend past 5 USD. It is tested end to end against a fake provider. No API key was available when
it was built, so there is no real-model number anywhere in this repo. See [Run it](#run-it).

## How it works

Every privileged action passes four rules, in order. The first that fails decides.

```
 agent proposes ──▶ 1 Identity ──▶ 2 Scope ──▶ 3 Bounds ──▶ 4 Provenance ──▶ world runs it
                        │             │            │              │
                        └──── BLOCK ──┴── BLOCK ───┴── BLOCK      └── ASK (pause for you)
                                                                              │
                                          every attempt ──▶ flight recorder (hash-chained receipts)
```

1. **Identity.** The agent carries a passport signed by its human, and a mandate signed for this
   agent only (Ed25519). Text cannot forge or widen it; an edited mandate fails verification.
2. **Scope.** The mandate lists the tools this agent may use. A job-application agent can't pay.
3. **Bounds.** Payees, recipients and targets must be on the mandate; spending must stay under
   the per-payment and total budget.
4. **Provenance.** Once the agent has read untrusted text, an action's destination must come
   from a trusted source (your request or the mandate). Otherwise Aurvane pauses and asks you.

**Asking you.** A held action waits in `Checkpoint.pending`. Your phone shows an Allow/Deny card;
in code, `checkpoint.approve("ask_1")` or `checkpoint.deny("ask_1")`. An approval re-checks rules
1 to 3 first, so it can never revive an expired mandate or break the budget.

**Sub-agents.** An agent can sign a sub-agent a mandate, but only a strictly narrower one: fewer
tools, less money, earlier expiry, never a payee or recipient the parent lacks. Every link verifies
back to the human's key, delegated money is reserved from the parent, a parent's taint flows to
the child, and revoking one link stops everything below it.

```python
from aurvane.delegation import delegate
checkout = delegate(buyer, "Checkout", "pays for one ticket", "Pay for the ticket", ["pay"],
                    merchants=["tickets.aiweek.example"], spend_limit=200, per_tx_limit=200)
delegate(buyer, "Greedy", "x", "x", ["pay"], spend_limit=900)   # DelegationRefused: wider than parent
```

## The code: one idea per file

| File | Idea | Lines |
|---|---|---:|
| [`aurvane/identity.py`](aurvane/identity.py) | Passports and signed, expiring mandates | 168 |
| [`aurvane/guard.py`](aurvane/guard.py) | The four rules: ALLOW, BLOCK or ASK | 150 |
| [`aurvane/recorder.py`](aurvane/recorder.py) | Tamper-evident flight recorder and trust score | 68 |
| [`aurvane/world.py`](aurvane/world.py) | A fake world: postings, stores, inbox, wallet | 59 |
| [`aurvane/agent.py`](aurvane/agent.py) | The checkpoint, approvals, and the loop | 178 |
| [`aurvane/delegation.py`](aurvane/delegation.py) | Narrower sub-mandates, chains back to the human, revocation | 158 |
| [`aurvane/models.py`](aurvane/models.py) | Claude, Grok, Ollama behind one plug, with a hard spending cap | 173 |
| [`aurvane/bench.py`](aurvane/bench.py) | 60 tasks, six attacks, with and without Aurvane | 219 |
| [`aurvane/stats.py`](aurvane/stats.py) | Summaries, H1 to H3, exact McNemar | 99 |
| [`ui/guard.js`](ui/guard.js) | The four rules in JavaScript, proven to match Python on all 60 tasks | 124 |

Plus [`aurvane/mcp_server.py`](aurvane/mcp_server.py): Aurvane as a Model Context Protocol server, so
Claude Desktop, Claude Code or any MCP client gets the same checkpoint. The demo page is built from
`ui/` (markup, style, room, replay, try-it box). New to the code? Start with **[LEARN.md](LEARN.md)**.

## Run it

```bash
pip install -e ".[dev,mcp]"
pytest -q                                     # 40 tests: rules, forgery, delegation, approvals, cap, JS parity, README numbers
python -m aurvane.bench                       # offline, worst-case agent, about 0.5 s
python ui/build.py && open ui/index.html      # the demo page: replay and try-it box
python ui/record.py                           # the film (Playwright + ffmpeg)

# Real models, same harness (protocol fixed in bench/PROTOCOL.md). Hard cap: 5 USD across all runs.
ANTHROPIC_API_KEY=...  python -m aurvane.bench --provider anthropic --model claude-haiku-5-5   # first: cents
ANTHROPIC_API_KEY=...  python -m aurvane.bench --provider anthropic --model claude-sonnet-5-5  # then, if budget is left
XAI_API_KEY=...        python -m aurvane.bench --provider xai --model <grok-model> --price <in>,<out>
                       python -m aurvane.bench --provider ollama --model qwen2.5:7b

python -m aurvane.mcp_server                  # Aurvane as an MCP server (stdio)
```

## Limits

- The headline numbers come from a simulated worst-case agent. Real-model runs measure how often
  real agents fall for injections and what Aurvane costs them; they have not been run yet.
- The two "scripted" runs on the demo page (a held email you deny, a sub-agent that tries to
  widen) use the real guard but are not benchmark tasks. No headline number comes from them.
- The browser guard checks expiry and agent binding but not Ed25519 signatures; Python verifies
  those when the page is built.
- Provenance matching is string-based: it knows a value came from untrusted text if that text
  contains it. A model that transforms a value (spells out a number, encodes an address) can
  defeat matching; the hard bounds in rule 3 still apply.
- Aurvane protects actions, not content. A summary or letter can still be quietly wrong.
- Signing keys live in memory, and the revocation list is an in-process object. A production
  version needs key storage (an HSM or secure enclave) and a revocation list verifiers can fetch.

## Where this goes

Intelligence is getting cheap; delegated trust is the scarce part. People will hand agents real
money only if they know **who** the agent is, that it **can't exceed** what they allowed, and that
they can **see** everything it did. Aurvane is those three things. See [docs/vision.md](docs/vision.md).

Built by [Sherif Morsi](https://shmorsi.github.io). MIT licensed.
