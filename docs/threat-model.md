# Threat model

One page: what Aurvane defends, against whom, how, and where it stops. Results quoted here come
from `bench/results/`, and all of them are simulated.

## What we protect

1. **Money**: payments an agent makes for a person.
2. **Data**: where files, messages and applications are sent.
3. **The record**: an honest log of what the agent did and why it was allowed.

## Who attacks

| Attacker | Can do | Cannot do |
|---|---|---|
| **Page author** (the main one): writes a job posting, store page, email or document the agent reads | Put any text in front of the agent, including hidden text, and make a gullible model propose any action | Get the human's or a parent agent's private key, or change code |
| **Hijacked agent**: a model that fully obeys the attacker | Propose any tool call, sign things with its *own* key, ask for more power | Sign as its parent or the human |
| **Curious sub-agent**: a helper bot that was handed a task | Use its own mandate, try to delegate further | Get a mandate wider than its parent's |

**Out of scope:** someone who controls the machine running the guard, the human's keys, or the
tool implementations themselves. The guard is trusted code. If it is bypassed, nothing here helps.

## The defence in one sentence

An agent may read anything, but **untrusted text can never choose where money or data goes**:
every privileged action is checked against a signed mandate (rules 1 to 3), and any destination
that only untrusted text could have chosen is held for a human (rule 4).

## How each attack is met

| Attack | Stopped by | Evidence |
|---|---|---|
| Pay or email a stranger | Rule 3, payee and recipient lists | benchmark: exfiltrate, overspend, 0 landed |
| Send the application elsewhere | Rule 3, targets | benchmark: redirect, 0 landed |
| "Your budget was raised" | Rule 1: a signature covers the old limit | benchmark: forge, 0 landed |
| Use a tool the task doesn't need | Rule 2, scope | red team: wrong tool |
| Address only the page mentions (lists not fixed) | Rule 4: held for you | red team: disguised, split, look-alike |
| Stolen or expired mandate | Rule 1: agent binding and expiry | red team: stolen, expired |
| Sub-agent signs itself more power | Chain check: every link must be signed by the agent above | tests: `test_self_signed_wider_mandate_is_blocked` |
| Parent hands out more than it has | Narrowing check plus budget reservation | tests: `test_delegated_budget_is_reserved_from_the_parent` |
| Launder an address through a helper | Taint flows to the child | red team: launder via sub-agent |
| Edit the log afterwards | Hash chain: `verify()` fails | tests: `test_recorder_detects_tampering` |

## Residual risk: what still gets through (shown on purpose)

1. **Amounts at a payee you trust.** If the page picks the amount, the payment is allowed and
   labelled "bounded". The signed budget caps it: 135 CAD in the benchmark, at most 225 CAD in the
   red team's ten-small-charges attack, never more than the budget.
2. **What you send to a place you trust.** Attaching your transcript to the real application
   gets through. Aurvane controls *where* data goes, not *what* goes there.
3. **Words.** A rewritten cover letter, or a lie in a note to you, gets through. Aurvane guards
   actions, not prose.
4. **Value rewriting at scale.** Rule 4 matches strings. A value the model rewrites so it still
   matches something the human wrote could slip past it. Rules 1 to 3 still hold.
5. **Approval fatigue.** If people tap Allow on everything, rule 4 becomes theatre.

## What would make it stronger

- Tag values as they leave untrusted tool results and carry the tags through the loop (data-flow
  tracking, as in CaMeL), instead of matching strings.
- Content rules for the "what": for example, never attach files marked private to an outbound
  action unless the mandate names that file.
- Keys in secure hardware, a revocation service that counterparties can query, and an anchored
  log head, so even the operator can't quietly rewrite history.
- Rate limits and per-merchant caps, so "many small charges" stops earlier than the budget.
