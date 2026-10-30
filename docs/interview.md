# Talking about Aurvane in an interview

Everything here can be checked in this repo. The only measured number is the simulated
worst-case benchmark in `bench/results/worst-case_summary.json`. Say "simulated" every time you
quote it, and say "not run yet" when asked about real models.

## The 30-second pitch

> AI agents now read web pages and then act: they pay, apply, send email. One hidden sentence on a
> page can steer them. I built Aurvane, a trust layer that sits between an agent and its tools.
> The agent can read anything, but untrusted text can never choose where money or data goes. Each
> agent carries a signed mandate, every action passes four rules, and everything lands in a
> tamper-evident log. Against a simulated agent that obeys every injected instruction, attacks
> that landed fell from 30 of 30 to 7 of 30, and the 7 are the cases I show on purpose: prose
> rewrites and small charges capped by the budget.

## The 2-minute pitch

> **Problem.** Agents run longer every year, so they read more untrusted text and act with less
> supervision. Prompt injection is OWASP's top LLM risk, and filters that catch 95% of attacks
> still lose to an attacker who retries.
>
> **Idea.** Don't try to make the model immune. Make the *actions* safe. Aurvane gives each agent a
> passport and a mandate signed with Ed25519: which tools, how much money, which payees,
> recipients and targets, until when. Before any tool call, a guard checks four rules in order:
> identity, scope, bounds, and provenance. Provenance is the interesting one: once the agent has
> read untrusted text, any destination it picks must come from the human or the mandate,
> otherwise Aurvane pauses and a phone-style card asks the human to allow or deny.
>
> **Sub-agents.** An agent can delegate, but only a strictly narrower mandate, and the chain
> verifies back to the human's key. Delegated money is reserved from the parent, and revoking one
> link stops everything below it.
>
> **Evidence.** A 60-task benchmark, fixed before any real-model run with written hypotheses.
> With a worst-case agent, 30 of 30 attacks land without Aurvane and 7 of 30 with it, money lost
> drops from 12,135 to 135 CAD, and all 30 clean tasks still complete with zero false alarms. 39
> tests, CI on every push, and the guard is ported to JavaScript for the live demo, with a test
> that proves both versions make the same decision on every action in all 60 tasks.
>
> **Honest limits.** That benchmark measures the guard, not a model; the real-model harness is
> built and capped at 5 USD but has not been run. Provenance is string matching, so a model that
> rewrites a value can slip past it, though the hard bounds still hold.
>
> **Why it matters.** Banks and fintechs are deploying agents now, and in Canada OSFI's E-23
> covers AI models from May 2027. Signed limits and a readable audit trail are exactly the
> evidence they will need.

## 15 hard questions

**1. Your headline number comes from an agent you wrote to fail. Isn't that rigged?**
It is a worst case on purpose. That agent obeys every injection, so any attack the guard misses
will land; it isolates the guard. It says nothing about how often a real model falls for an
injection. That is H1 in `bench/PROTOCOL.md`, and I have not run it, so I don't claim it.

**2. Why not just train or prompt the model to ignore injections?**
Do that too. But a prompt is text and can be overridden by text, and a filter that is 95% right
loses to retries. Aurvane's checks run in code on the action, so they hold even when the model is
fooled. Defense in depth: model-level hardening reduces attempts, Aurvane bounds the damage.

**3. What does Aurvane not stop?**
Content. It guards actions, not prose: a cover letter can still be rewritten (4 of the 7). And
when untrusted text only picks the amount at a payee you already trust, it is allowed but
labelled "bounded"; the signed budget caps the loss (3 of the 7, 135 CAD). Both are shown.

**4. How does provenance work, and how would you break it?**
After the first untrusted read, every destination (payee, recipient, posting) must appear in a
trusted source: the human's request or the mandate. It is whole-token string matching. To break
it, get the model to transform the value, for example spell an address out or split it. Then the
value is "unknown", which still triggers ASK, but a value the human also wrote could collide. The
stronger fix is data-flow tracking like Google DeepMind's CaMeL.

**5. Why Ed25519 and canonical JSON?**
Ed25519 is fast, has small keys and is hard to misuse. Canonical JSON (sorted keys, fixed
separators) makes one meaning serialize to one byte string, so a signature can't verify one way
and fail another. Without it, verification would be flaky.

**6. Your JavaScript guard doesn't verify signatures. Isn't that a hole?**
In the demo page, yes, and I say so. Python verifies passport and mandate when the page is built
and passes the result in. Doing it in the browser needs WebCrypto Ed25519 plus byte-identical
canonical JSON, and JavaScript prints `250.0` as `250`. For a static demo, I chose correctness
of the other rules, proven by a parity test, over a fragile signature check.

**7. How do you know the JS and Python guards agree?**
`tests/test_js_guard.py` runs all 60 tasks through the Python checkpoint, records every guard
call, adds about 20 probe actions per task, then replays them into the JS guard in Node: 1,643
decisions. Any difference in outcome, rule, reason text or the bounded flag fails the test. I
checked that it catches a one-character change (`>` to `>=`).

**8. What stops a sub-agent from giving itself more power?**
Its mandate must be signed by its parent's key, which the parent's passport (signed by the human)
names. A self-signed mandate fails that check. A wider one fails the narrowing check on every
dimension: tools, money, per-payment limit, expiry, currency, payees, recipients, targets.

**9. Why reserve delegated budget from the parent?**
Otherwise a parent with 250 CAD could give 250 to each of ten children, and the family could
spend 2,750. Reservation keeps the total under what the human signed.

**10. What happens when the human taps Allow?**
The value they approved becomes trusted, then rules 1 to 3 run again before the action. So an
approval cannot revive an expired mandate or break the budget. The MCP server does not expose
approve, because the model on the other side must never approve its own held action.

**11. How do you keep real-model runs from costing too much?**
Before each call, the cap prices the worst case: the whole prompt at about three characters per
token, plus all 4,096 output tokens. If that could cross 5 USD in total, the call is not made and
the run is marked `stopped_early`. Spend is kept in a ledger, so the cap holds across runs.

**12. How would you test H3, that Aurvane doesn't hurt normal tasks?**
Paired: each clean task runs with and without Aurvane. Only pairs that disagree carry
information, so I use an exact McNemar test on those. The protocol allows a drop of at most 2 of
30. With the worst-case agent there are no disagreeing pairs, so p = 1.0, which is uninformative,
not good news.

**13. Is the flight recorder secure?**
It is tamper-evident, not tamper-proof: each event stores the hash of the previous one, so any
edit breaks `verify()`. Someone who can rewrite the whole log can recompute the chain. A
production version would anchor the latest hash somewhere the agent can't write, or sign it.

**14. AP2, Visa and Mastercard already have mandates for agents. Why would anyone use this?**
They standardize the payment envelope. Aurvane is the enforcement point inside the agent's
runtime, for every action, not only payments, plus provenance, narrowing delegation and a log.
The honest plan is to read and write AP2-style mandates, not compete with them.

**15. What would you do next?**
Run the real-model benchmark (Claude first, under the cap). Replace string provenance with value
tagging through the tool loop. Persist keys and revocations behind a small service so a
counterparty can check a mandate the way a terminal checks a card.

## How this maps to AI engineering intern roles in Canada

Large Canadian employers (RBC, TD, CIBC, BMO, Scotiabank, Shopify, Wealthsimple) hire AI and ML
engineering interns for work that usually includes some of the following. Each line says where
the evidence is in this repo.

| What the role usually asks for | Where Aurvane shows it |
|---|---|
| Python, testing, CI | `aurvane/`, 39 tests in `tests/`, GitHub Actions on every push |
| Building on LLM APIs and tool use | `aurvane/models.py`: Claude, Grok and Ollama behind one interface, tool calls, prompt caching, cost tracking |
| Agent systems and MCP | `aurvane/agent.py` loop, `aurvane/mcp_server.py` |
| Evaluation design and statistics | `bench/PROTOCOL.md` written before results, paired tasks, exact McNemar in `aurvane/stats.py` |
| Security and responsible AI | the four rules, signed mandates, provenance, OWASP LLM01 and LLM06 |
| Model risk and governance (banks) | hash-chained audit log, signed limits, human approval, E-23 context in `docs/vision.md` |
| Payments and commerce (fintech, Shopify) | budgets, per-payment limits, payee allow-lists, delegated budgets |
| Front-end and communication | the demo page, the try-it box, the film, the README and `LEARN.md` |

For a bank, lead with governance and audit (questions 10, 13, 14). For Shopify or a fintech,
lead with payments and delegation (questions 8, 9, 11). For a research-flavoured team, lead with
evaluation honesty (questions 1, 7, 12).
