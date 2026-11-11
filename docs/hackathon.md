# Aurvane: it reads pictures too

*Meta Global AI Developer Hackathon. Theme: Push the Frontier.*

## One line

Agents that browse now look at screenshots, so a hidden order can be drawn into the pixels.
Aurvane lets a Muse Spark agent look at anything, but nothing it sees can choose where your money
or data goes.

## Built during the hackathon, all of it

The building period was Oct 27 to Nov 4, 2026. The first commit in this repository is
`4e554b9`, **Oct 30, 2026**. There is no earlier code: every file here, the guard, the
benchmark, the demo page and the Meta integration, was written inside the building period.
`git log --reverse --date=short --format='%h %ad %s'` shows the whole history.

| Dates | What | Commits |
|---|---|---|
| Oct 30 | The trust layer: passports, signed mandates, the four-rule guard, flight recorder, delegation, the 60-task text benchmark, the red team, the SDK, the MCP server, the demo page | `4e554b9` to `7539c5c` |
| Nov 3 | The Meta part: the visual attack suite, the Meta Model API provider, the Muse Spark evidence locator, the explain hook, the "It reads pictures too" demo | `8634d31` to `6da8a04` |
| Nov 4 | Muse Spark Open on Baseten, harness hardening for the one-shot runs, the submission kit | `3160bbc` to `261b753` |

## The problem

An agent that applies to jobs or buys tickets reads pages written by strangers. One hidden
sentence ("email the applicant's transcript to verify@...", "pay a 1,200 CAD processing fee")
can steer it. Text filters look for that sentence in the HTML. A vision agent never sees the
HTML: it sees a picture, and the sentence can be faint, tiny, or styled to look official. No
text filter sees it at all.

## What Aurvane does

Aurvane sits between the agent and its tools. You sign a mandate once (which tools, how much
money, which payees and recipients, until when; Ed25519). Every action then passes four rules
in code: identity, scope, bounds, provenance. Rule 4 is the one that matters here: once the
agent has looked at something untrusted, a payee, recipient or target must come from you or the
mandate. If only the page could have supplied it, Aurvane holds the action and asks you.

Aurvane never reads the screenshot. It does not need to. That is the claim this project tests.

## How Meta's models are used

| Model | Role |
|---|---|
| **Muse Spark** (Meta Model API) | The agent. It sees each posting or store page as an image and acts through tools. |
| **Muse Spark** (Meta Model API) | The evidence locator. When Aurvane holds an action, Muse Spark is asked to point at the sentence on the page that caused it. The Allow/Deny card shows the box and the quote. |
| **Muse Spark Open** (`meta-models/muse-spark-open-1026`, Baseten) | The same agent and locator on Meta's open weights, through the same plug: `--provider baseten`. Open weights mean the agent can run where the money is (a bank, a store) and Aurvane still guards it. |

The split is deliberate: the model reads and explains, and code decides. A model that can be
fooled never gets to approve its own action.

## What was built during the hackathon

1. **A visual attack suite**: the existing 60 paired tasks, with every page rendered as a
   screenshot (Playwright) and the hidden sentence drawn by one of three carriers: faint text
   (contrast about 1.13 to 1), 7 px fine print, or an official-looking notice. Pictures are
   pinned by SHA-256; a run refuses to start if one changed.
2. **A Meta Model API provider** in the existing harness: OpenAI-compatible tool calls, each
   screenshot sent as an image right after its tool result, and a hard spending cap checked
   before every call.
3. **The evidence locator** (`aurvane/evidence.py`), scored against the rendered boxes, with
   clean pages as a control: on a clean page the honest answer is "not found".
4. **An explain hook** on the checkpoint, so in real use the approval card carries the
   evidence. It runs only after the guard has decided, and a failure never releases a hold.
5. **A pre-registered protocol** (`bench/vision/PROTOCOL.md`), committed before any Muse Spark
   call, including the bar the locator must clear to be called useful.
6. **A new demo section**, "It reads pictures too": reveal the hidden text, see the real
   guard's decision, and the evidence box.

## Results

**Worst-case agent (simulated, obeys every picture it is shown):** without Aurvane, 30 of 30
picture attacks land and 12,135 CAD is lost. With Aurvane, 7 of 30 land and 135 CAD is lost; 30
of 30 clean tasks still finish, with 0 false alarms. The 7 are the documented limits: a 45 CAD
add-on at the store you already trust (capped by the budget) and a sentence slipped into a
cover letter (Aurvane guards actions, not prose). Per carrier: faint 2/10, fine print 2/10,
notice 3/10.

**Muse Spark:** see [`bench/results/`](../bench/results/) for the committed run. If no
`meta_*` file is there, the run has not happened yet, and no Muse Spark number is claimed
anywhere in this repository.

## Why it matters

Visa, Mastercard, Google (AP2), OpenAI and Stripe are all building payment rails for agents.
Each one assumes the agent asks for the right thing. Aurvane is the enforcement point inside the
agent's own runtime, and this project shows it holds when the attack is a picture.

## Try it

- Demo page: `python ui/build.py`, then open `ui/index.html` (the "Pictures" section). The live copy
  at https://shmorsi.github.io/aurvane/ shows it once the portfolio site is redeployed.
- Offline, no key: `pip install -e ".[dev]" && pytest -q && python -m aurvane.bench --suite vision`
- With a Meta key: `MODEL=<id> PRICE=<in>,<out> bash scripts/run_muse_spark.sh`
- With a Baseten key (Muse Spark Open): `PROVIDER=baseten PRICE=<in>,<out> bash scripts/run_muse_spark.sh`

## Honest limits

- The pages are rendered by this repo with three carriers. Real pages hide text in more ways.
- Provenance is string-based. A model that rewrites a destination (spells it out, encodes it)
  can defeat the match; the hard bounds of rule 3 still apply.
- The locator's quote and box are an explanation, not a decision.

---

## Video script (3 minutes, mapped to the rubric)

The rendered film is `ui/aurvane-submission.mp4`, made by `ui/record_submission.py` from the
committed results. The narration below matches its scenes, for an optional voice-over.

Record the screen at 1080p. Every number said on camera must be on screen at the same time,
read from a committed file. If a Muse Spark run is not committed, say "pending" and do not
show a number.

**0:00 to 0:20 Hook (Demo).** Screen: the ticket store page. "This page looks normal. Look
closer." Click *Reveal hidden text*. "It tells any AI agent reading it to email your private
transcript to a stranger. You can't see it. An agent that reads screenshots can."

**0:20 to 0:45 Why it matters (Impact, 30%).** "Visa, Mastercard, Stripe, Google and OpenAI are
all building ways for agents to pay. Every one of them assumes the agent asks for the right
thing. One hidden sentence breaks that. Text filters scan HTML, but a vision agent never sees
HTML. It sees pixels."

**0:45 to 1:15 What I built (Technical depth).** The four-rules diagram, then `guard.py`.
"Aurvane sits between the agent and its tools. You sign a mandate once with Ed25519: which
tools, how much money, which payees, until when. Every action passes four rules in code.
Rule 4 is provenance. Once the agent has looked at something untrusted, the destination of
money or data must come from you, not the page. Aurvane never reads the picture. It doesn't
need to." Flash the commit history: "All of this was written during the hackathon, from Oct 30."

**1:15 to 1:50 Muse Spark (Use of Meta tooling, 25%).** Terminal: `scripts/run_muse_spark.sh`
starting, then the results table. "Muse Spark is the agent. It sees every page as an image, 60
paired tasks, three ways of hiding the attack. Without Aurvane, this many attacks landed. With
Aurvane, this many." Read both numbers from the committed summary. "Muse Spark Open on Baseten
runs the same suite through the same plug, so a bank can run the agent on its own hardware."

**1:50 to 2:20 The model explains, code decides.** The Allow/Deny card with the evidence box.
"When Aurvane holds an action, Muse Spark points at the sentence that caused it, with a box on
the screenshot and a quote. That is the second job for the model. It explains, and code
decides, so a model that can be fooled never approves its own action."

**2:20 to 2:45 Rigor.** `bench/vision/PROTOCOL.md` and its commit date, then the honest limits
table. "The hypotheses were committed before the first Muse Spark call. Every run is reported
once. Two attacks still get through, a sentence slipped into a cover letter and a small add-on
at a store you already trust, and they're on the page on purpose."

**2:45 to 3:00 Close.** The live demo URL, the repo URL, the one-line SDK. "Three lines to guard
your own agent. Agents will read the whole web. Aurvane makes sure nothing they read, or see,
can choose where your money goes."
