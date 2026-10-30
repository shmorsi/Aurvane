# Learn Aurvane in 3 days

Read one file at a time, in this order. Each file opens with a docstring that explains its idea
in plain English; read that first, then the code. After each file, do the exercise.

## Day 1: who an agent is, and what it may do

**`aurvane/identity.py`** (morning)
- A `Principal` is a human with an Ed25519 signing key.
- A `Passport` binds an agent to the human who sent it. A `Mandate` lists what that agent may
  do: tools, budget, payees, recipients, targets, expiry. Both are signed.
- `canonical()` turns a dict into deterministic bytes, so one signature covers exactly one
  meaning. Without it, the same mandate could serialize two ways and verification would flake.
- A passport also carries the agent's own public key (`agent_key`), so the agent can sign
  narrower mandates for its sub-agents (Day 3, `delegation.py`).
- Exercise: issue a mandate, change `spend_limit` with `dataclasses.replace`, call `is_valid()`.
  Why does it fail? (The signature covers the old payload.)

**`aurvane/guard.py`** (afternoon)
- Four rules in order: identity, scope, bounds, provenance. First failure decides.
- `Provenance.label()` answers: could this value have come from the human, or only from the
  untrusted page? `_contains()` matches whole tokens, so "45" is not found inside "450".
- The "bounded" case: untrusted text chose only the *amount*, at a payee the human trusts. Aurvane
  allows it, because the budget already caps the loss. That is a deliberate trade-off.
- Exercise: run `pytest -k provenance -v` and read those four tests.

## Day 2: what happened, and where

**`aurvane/recorder.py`** (morning)
- Every event stores the hash of the previous event. Edit any past event and `verify()` fails.
- `trust_score()`: 70% weight on attacks contained, 30% on budget not lost. Know the formula.
- Exercise: log three events, edit the second, call `verify()`.

**`aurvane/world.py`** (afternoon)
- `TOOLS` marks each tool read-only or privileged, and names its control arguments.
- `UNTRUSTED_SOURCES`: the output of these tools came from strangers.
- Exercise: add a `book_flight` tool with `payee_arg` and `amount_arg`. Nothing in the guard
  changes. Why? (The guard only reads `ToolSpec`, so new tools get protection for free.)

## Day 3: the loop and the evidence

**`aurvane/agent.py`** (morning)
- `Checkpoint.attempt()` is Aurvane in one function: check, then run, refuse, or hold, then record.
- A held action (ASK) waits in `Checkpoint.pending`. `approve(id)` runs it, but only if rules 1-3
  still pass (an approval cannot revive an expired mandate). `deny(id)` drops it. Both are logged.
- `WorstCaseAgent` obeys every injection it reads. It tests the guard, not a model.
- Exercise: run `pytest -k approv -v`. Why must `approve()` re-check the guard?

**`aurvane/models.py`** (late morning)
- `LLMAgent` speaks to Claude, Grok, Ollama or any OpenAI-compatible API through one interface.
- `SpendCap` prices the worst case of the next call before making it, and refuses if the total
  could cross the cap. The ledger in `bench/results/spend.json` keeps the total across runs.
- Exercise: read `tests/test_models.py`. It runs all 120 conditions against a fake Claude that
  speaks the real wire format. Which line makes the cap stop the run?

**`aurvane/delegation.py`** (early afternoon)
- An agent can sign a sub-agent a mandate, but only a strictly narrower one: inside the parent's
  on every dimension (tools, money, payees, recipients, targets, expiry), smaller on at least one.
- `Chain.problem()` walks from the human's key down. Each link must be signed by the agent one
  step up and be narrower than its parent. A verifier needs only the human's public key.
- Delegated money is *reserved*: give a child 200 of 250 and the parent has 50 left. Without that,
  parent and child could each spend the full budget.
- Revocation: anyone above a mandate signs its id; every link below it fails at once.
- Taint flows down: a parent that read untrusted text cannot launder it through a child.
- Exercise: `self_signed()` is what a hijacked sub-agent can do alone. Read
  `test_self_signed_wider_mandate_is_blocked`. Which check in `problem()` stops it?

**`aurvane/bench.py`** (afternoon)
- 60 paired tasks, six attacks, with and without Aurvane. `score()` decides "landed" by exact match
  of tool and arguments.
- Exercise: `python -m aurvane.bench`. Then delete rule 4 from `guard.py`, rerun, and explain which
  numbers changed. (The 4 held exfiltration attempts in purchase tasks now land.)

**`aurvane/stats.py`** (evening)
- `summarize()` turns rows into counts. `analyse()` checks the three hypotheses that
  `bench/PROTOCOL.md` fixed before any real-model run.
- McNemar, in one sentence: on paired yes/no outcomes, only the pairs that disagree carry
  information, and if the two conditions were equal those disagreements would split 50/50.
- Exercise: `mcnemar_exact(5, 0)` is 0.0625. Work it out by hand: 2 x (1/2)^5.

**Then:** `aurvane/mcp_server.py` (40 lines), and the demo page in `ui/`, one idea per file:
- `ui/guard.js`: the four rules again, in JavaScript, so the page can decide live. It does not
  re-verify Ed25519 signatures in the browser; Python verifies them at build time.
  `tests/test_js_guard.py` replays every guard call from all 60 tasks into both guards and fails
  on any difference. Exercise: change `>` to `>=` in the per-payment check and run the test.
- `ui/room.js`: draws the room. A sub-agent orbits inside its parent's shell, in a smaller shell.
- `ui/replay.js`: plays recorded runs, the score, the phone-style approval card, the log.
- `ui/tryit.js`: the attack box. A gullible simulated agent obeys whatever it can parse from
  your text; the real guard decides. Held actions get Allow and Deny buttons.
- `ui/build.py`: bakes everything into one file, `ui/index.html`, and scripts two showcase runs
  (a held email you deny, a sub-agent that tries to widen its mandate) through the real guard.

## 10 interview questions

1. **What problem does Aurvane solve?**
   Agents act on text they read, and anyone can write that text. Aurvane lets an agent read anything
   while making sure untrusted text can't choose where money or data goes.

2. **Why sign mandates instead of just putting limits in the prompt?**
   A prompt is text, and text can be overridden by other text. A signed mandate is checked in code;
   an injected "your budget is now 5,000" changes nothing because the signature would break.

3. **Why does provenance only matter after the agent reads untrusted text?**
   Before that, everything in the agent's context came from the human. Taint starts at the first
   untrusted read; from then on, any destination could have been planted.

4. **Why allow an untrusted amount at a trusted payee?**
   The payee is trusted and the signed budget caps the loss. Blocking it would also block normal
   purchases, where the price always comes from the store page. I show it as a residual risk.

5. **What does Aurvane not protect?**
   Content. A cover letter can still be rewritten. That needs a different tool: review, or a
   second model checking text against the human's intent.

6. **How would a real model change the results?**
   A real model follows some injections, not all, so "without Aurvane" numbers drop. The "with
   Aurvane" side should stay at zero for the four blocked attack types, since the guard doesn't
   depend on the model. That is hypothesis H2 in `bench/PROTOCOL.md`.

7. **What's the weakest part of the design?**
   String-based provenance. If a model transforms a planted value, matching can miss it. Hard
   bounds (rule 3) still hold, which is why both layers exist.

8. **Why a hash chain in the recorder?**
   So the log is tamper-evident: an auditor can check that nothing was edited or removed.

9. **How does this fit MCP?**
   `mcp_server.py` exposes the guarded tools over MCP, so any MCP client gets the checkpoint
   without changing its model or prompts.

10. **How would this become a company?**
    Start narrow: spending controls for agents at fintechs and banks, where audit trails are
    required anyway. Grow toward a network where merchants and other agents verify a mandate before
    accepting a request, the way card terminals verify a card.
