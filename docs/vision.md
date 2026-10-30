# Where Aurvane goes

*The trust layer for the agent economy.* This page argues for that line, then argues against it.
Every outside fact has a numbered source at the bottom. Facts about Aurvane itself come from this
repo; the only measured number is the simulated worst-case benchmark in `bench/results/`.

## 1. The bottleneck is delegated trust, and it grows with task length

- **Agents are running longer.** METR measured the length of task (in human time) that frontier
  agents finish half the time, and found it doubling roughly every seven months since 2019 [1].
  A longer run means more pages read, more tools called, and fewer moments where a person looks.
- **Every page read is a chance to be steered.** OWASP ranks prompt injection first among risks
  to LLM applications, and lists "excessive agency" (too much functionality, permission or
  autonomy) as its own entry [2]. Simon Willison's "lethal trifecta" names the dangerous mix:
  private data, untrusted content, and a way to send things out [3]. He also argues that a
  filter that stops 95% of attacks is a failing grade when attackers can retry [3].
- **So the limit is not intelligence.** A person will hand an agent a card, an inbox or a
  production system only if they know who the agent is, that it cannot exceed what they
  allowed, and that they can see what it did. That is what Aurvane's three words mean: signed,
  bounded, visible.

Research agrees with the shape of the fix. Google DeepMind's CaMeL separates the trusted request
from untrusted data, tracks where every value came from, and checks a policy before each tool
call [4]. Aurvane's rule 4 (provenance) is a much simpler cousin of that idea, and the honest
comparison is that CaMeL's data-flow tracking is stronger than Aurvane's string matching.

## 2. The payment rails for agents are being built right now

- Visa (Intelligent Commerce) and Mastercard (Agent Pay, with "agentic tokens") both launched
  agent payment programs at the end of April 2025 [5][6].
- Google's Agent Payments Protocol (AP2), released in September 2025 with more than 60 partners,
  records what the user asked for and what they approved as signed *mandates* (an intent mandate,
  a cart mandate) and calls the chain a non-repudiable audit trail [7][8].
- OpenAI and Stripe released the Agentic Commerce Protocol with Instant Checkout in ChatGPT,
  using a shared payment token so the agent never sees the card [9]. Shopify and Google followed
  with the Universal Commerce Protocol in January 2026, and Shopify now offers "agentic
  storefronts" that sell inside AI assistants [10][11].

**What this means for Aurvane.** The word "mandate" is now industry vocabulary, and the big
players own the payment envelope. Aurvane should not try to replace AP2 or a card network. The
part they leave to whoever builds the agent is the enforcement point *inside* the agent's runtime:

1. checking **every** action, not only payments (emails, file shares, applications, API calls)
   against a signed scope at the moment the agent takes it;
2. knowing which values came from untrusted text, and pausing for a person when one of them
   chooses a destination;
3. letting an agent hand a sub-agent a strictly narrower mandate, verifiable back to the human,
   with budgets reserved and revocation that flows down;
4. a tamper-evident, plain-English log that a risk officer can read.

The right long-term move is to read and write AP2-style mandates, not to invent a rival format.

## 3. The wedge: spending controls and audit trails for agents at banks and fintechs

Canadian financial firms are deploying agents now, and regulation is arriving on a known date.

- **The regulator.** OSFI's Guideline E-23 on model risk management takes effect for every
  federally regulated financial institution on May 1, 2027, and its definition of "model"
  explicitly includes AI and machine learning [12]. Agents that move money or data will need an
  inventory, limits, monitoring and evidence. A signed mandate and a hash-chained log are evidence.
- **Open banking is getting write access.** Budget 2025 commits to completing the
  consumer-driven banking framework, moving oversight to the Bank of Canada and extending it to
  payment initiation ("write access"), with that phase targeted around mid-2027 [13]. Once a
  third party can initiate payments, an agent can too, and someone has to bound it.
- **The banks.** RBC ranked first in Canada and third of 50 global banks in the 2025 Evident AI
  Index [14]. In May 2026 TD launched its first agentic AI system, for mortgages and HELOCs: it
  sorts borrower documents, works out income and runs policy checks, then hands a memo to a human
  underwriter, and TD plans to extend agents through to funding [15]. CIBC took its
  in-house AI platform bank-wide in May 2025, launched an "Agents Marketplace" where staff build
  and share their own agents, and in July 2026 announced a pilot of an enterprise-wide agentic
  workspace [16][17].
- **The fintechs and platforms.** Shopify is putting its merchants' checkout inside AI
  assistants [10][11]. Wealthsimple runs an AI assistant, Willow, and is hiring for client-facing
  AI products; a third-party profile says Willow does not complete transactions yet [18]. The day
  it does is the day it needs a mandate.

**A first product someone would pay for:** a mandate service and checkpoint SDK for a bank's
*internal* agents. Every agent in a marketplace like CIBC's gets a passport, a signed mandate
(tools, money, counterparties, expiry), an approval route to a named employee, and a log that
exports into the model-risk inventory E-23 asks for. The buyer is model risk or operational risk,
not the innovation lab. Internal agents come first because the bank controls both ends, so no
outside party has to adopt anything.

## 4. The path to a verification network

Card networks are valuable because every transaction is checked against the same rules by a
party both sides trust. Visa processed about 258 billion transactions in fiscal 2025 [19]. If
agents start transacting with merchants and with each other, each request needs the same kind of
check: *is this agent who it says it is, does a human's signed mandate cover this exact action,
and has anyone up the chain revoked it?*

Steps, each useful on its own:

1. **In-house:** the SDK above, inside one bank or fintech.
2. **Counterparty checks:** merchants and APIs verify an incoming agent's mandate chain before
   they act. Aurvane's chain verification needs only the human's public key, which is the
   property that makes this possible.
3. **Issuers:** banks issue the human's key, because they already know their customer. A bank
   becomes the root of trust for its customers' agents, the way it issues their cards today.
4. **Network:** a revocation and verification service that answers "is this mandate still good?"
   in milliseconds, with a small fee per check, like a network fee on a card payment.

## 4b. How big could this get? The honest math

The ambition is a network that checks every agent transaction. The size of the prize is real, but
it is measured in **volume protected**, not in revenue:

- Visa, the largest card network, reported about **14.2 trillion USD** of payments volume and about
  **40 billion USD** of net revenue for fiscal 2025 [19][20]. That is roughly 0.3% of volume, after
  decades and billions of cards.
- So "trillions of dollars" is a plausible scale for the *payments that pass through mandate checks*
  if agents become a normal way to buy. It is not a plausible scale for one company's *revenue*.
  The largest payment network on Earth earns tens of billions.

A ladder that would be worth climbing, each rung a real business on its own:

| Rung | What it is | What would have to be true |
|---|---|---|
| 1 | Controls and audit evidence for internal agents at a few banks and fintechs | E-23-style rules make evidence mandatory; the SDK drops into their agent platform |
| 2 | The default policy layer for regulated firms' agents | Works across frameworks and models; passes security reviews; priced per agent |
| 3 | Counterparty verification: merchants and APIs check an agent's mandate before acting | A shared format (AP2-compatible) and a revocation service with very high uptime |
| 4 | A verification network with a small fee per check | Neutral governance, bank issuers as roots of trust, liability rules everyone accepts |

Each rung is less likely than the one before. Rung 1 is a realistic product. Rung 4 is what card
networks took decades to build, with banks as owners.

## 5. Risks

- **The incumbents build it.** Visa, Mastercard, Google, Stripe and Shopify already have the
  distribution and are adding mandates and agent tokens [5][6][7][9][10]. A free feature in AP2 or
  a card program beats a standalone product.
- **Agent frameworks absorb it.** Policy checks before tool calls are easy to add to any agent
  framework; the moat is not the code.
- **The provenance rule is weak against a smart attacker.** String matching misses values a
  model rewrites. Data-flow tracking like CaMeL's [4] is stronger and harder to integrate.
- **Approval fatigue.** If people get too many Allow/Deny cards they tap Allow on everything,
  and the human check becomes theatre.
- **Bank procurement is slow,** and a vendor that touches payments faces security reviews,
  audits and liability questions measured in quarters.
- **No real-model evidence yet.** The only number in this repo comes from a simulated agent.

## 6. What must be true

1. Agents get delegated real money and data at scale, not only in demos.
2. Firms want one policy layer across many agent frameworks and models, instead of each
   framework's own permissions.
3. Regulators (OSFI and its peers) accept signed mandates plus a tamper-evident log as evidence
   of control.
4. A neutral party, not one platform, is trusted to verify agent-to-agent requests.
5. Real models show friction low enough to keep: H3 in `bench/PROTOCOL.md` has to hold.

## 7. Honest odds

As a venture, the most likely outcome is that the payment networks and platforms ship most of this
themselves, and the odds that Aurvane in particular becomes the verification network are very
small. The odds that its ideas (narrower-only delegation, provenance checks, a readable audit
trail) become normal practice are much better, because the problems in section 1 do not go away.
The realistic value today is as a small, tested reference that shows the ideas working end to end,
and as a starting point for one narrow product: controls and evidence for internal agents at a
regulated firm.

## Sources

1. METR, "Measuring AI Ability to Complete Long Tasks" (March 2025), arXiv:2503.14499. <https://metr.substack.com/p/2025-03-19-measuring-ai-ability-to-complete-long-tasks>
2. OWASP Top 10 for LLM Applications 2025 (LLM01 Prompt Injection, LLM06 Excessive Agency). <https://genai.owasp.org/llm-top-10/>, summary: <https://www.promptfoo.dev/docs/red-team/owasp-llm-top-10/>
3. Simon Willison, "The lethal trifecta for AI agents" (16 June 2025). <https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/>
4. Debenedetti et al., "Defeating Prompt Injections by Design" (CaMeL), arXiv:2503.18813. <https://huggingface.co/papers/2503.18813>
5. American Banker, "How agentic commerce redefines AI's role in payments" (Visa and Mastercard launches). <https://www.americanbanker.com/payments/news/visa-mastercard-launch-payments-for-agentic-ai>
6. PYMNTS, "Visa, Mastercard, PayPal Fuel Agentic AI Commerce Boom." <https://pymnts.com/news/artificial-intelligence/2025/visa-mastercard-paypal-fuel-agentic-ai-commerce-boom>
7. Google Cloud, "Announcing Agent Payments Protocol (AP2)" (September 2025), as reposted: <https://en.10minhotel.com/2025/09/22/announcing-agent-payments-protocol-ap2-google-cloud-blog>
8. BankInfoSecurity, "Let AI Do the Shopping, Says Google." <https://www.bankinfosecurity.net/let-ai-do-the-shopping-says-google-a-29471>
9. Stripe, "Stripe powers Instant Checkout in ChatGPT and releases Agentic Commerce Protocol codeveloped with OpenAI." <https://stripe.com/newsroom/news/stripe-openai-instant-checkout>
10. Shopify, "AI commerce at scale." <https://www.shopify.com/news/ai-commerce-at-scale>
11. MediaPost, "Shopify, Google Co-Develop Agentic Shopping Standard" (Universal Commerce Protocol). <https://www.mediapost.com/publications/article/411923/shopify-google-co-develop-agentic-shopping-standa.html>
12. OSFI, "Guideline E-23 – Model Risk Management (2027)" and cover letter (published 11 September 2025, effective 1 May 2027). <https://www.osfi-bsif.gc.ca/en/guidance/guidance-library/guideline-e-23-model-risk-management-2027>
13. Department of Finance Canada, "Budget 2025: Canada's Framework for Consumer-Driven Banking." <https://www.canada.ca/en/department-finance/programs/financial-sector-policy/open-banking-implementation/budget-2025-canadas-framework-for-consumer-driven-banking.html>
14. RBC, "RBC ranks #1 in Canada and #3 globally for AI maturity among banks" (October 2025). <https://thoughtleadership.rbc.com/news/rbc-ranks-1-in-canada-and-3-globally-for-ai-maturity-among-banks>
15. Canadian Mortgage Trends, "TD launches agentic AI for mortgage and HELOC applications" (May 2026). <https://www.canadianmortgagetrends.com/2026/05/td-launches-agentic-ai-for-mortgage-and-heloc-applications/>; TD Stories: <https://stories.td.com/ca/en/article/agentic-ai>
16. CIBC, "CIBC launches in-house AI platform enterprise-wide after successful pilot" (27 May 2025). <https://ycharts.com/news/story/PRN-C8502-20250527>
17. Wealth Professional, "Bank pilots agentic AI workspace, calls it a Canadian banking first" (CIBC, July 2026). <https://www.wealthprofessional.ca/news/industry-news/bank-pilots-agentic-ai-workspace-calls-it-a-canadian-banking-first/393179>
18. Wealthsimple Q1 2026 results (AI support tools) and a third-party profile of Willow. <https://www.newsfilecorp.com/release/296531>, <https://www.wealthprofessional.ca/company-profiles/wealthsimple/393446>
19. Visa Inc., Form 10-K for fiscal 2025. <https://www.sec.gov/Archives/edgar/data/1403161/000140316125000089/v-20250930.htm>
20. Visa Inc., Fiscal 2025 Annual Report (payments volume and net revenue table). <https://s29.q4cdn.com/385744025/files/doc_downloads/2025/Visa-Fiscal-2025-Annual-Report.pdf>

Some sources above are secondary coverage of an announcement rather than the announcement itself;
they are marked by publisher. Check the primary page before quoting a date or a partner list.
