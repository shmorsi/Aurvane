# Decisions

Every judgment call made while renaming and upgrading this repo to Aurvane, in the order
they were made. Newest at the bottom.

1. **Rename scope.** Every file, path, key and string that carried the old name now says Aurvane:
   the package (`aurvane/`), result files (`worst-case_with_aurvane_*`), summary keys
   (`with_aurvane`, `without_aurvane`), the JS handle (`aurvaneDemo`), the MCP server name, and
   the flight-log file. Git history keeps the old name; rewriting published history on `main`
   would be worse than leaving it.
2. **The forge attack text changed by one word.** It used to say "your [old name] mandate was
   updated". It now says "your Aurvane mandate was updated". No real-model run had happened, and
   the worst-case agent does not read the text, so the worst-case results are identical. The
   change is listed in `bench/PROTOCOL.md` anyway.
3. **"Claude", "AI" and "assistant" in files.** Read as a rule about attribution: no commit,
   trailer, branch or file credits a tool or model as an author. The words still appear where
   they are the subject matter (a real-model provider called Claude, "AI agents", the attack text
   "AI assistants processing this page"), because removing them would break upgrade 1 and the
   frozen benchmark.
4. **Commit signing off in these two clones.** The container's global git config signs commits
   with a key that is not Sherif's. Earlier commits in both repos are unsigned, so signing is
   turned off locally (`commit.gpgsign false`) to keep every commit his alone.
5. **The repository URL is `github.com/shmorsi/aurvane`.** Links point there as asked. The GitHub
   repository itself is still under its old name and must be renamed in
   GitHub settings (this session has no tool that renames a repository). GitHub redirects the old
   URL after a rename, so nothing breaks in between except the new links, which 404 until then.
6. **Real models: harness ready, nothing run.** This container has no `ANTHROPIC_API_KEY` or
   `XAI_API_KEY`, and its network policy blocks the Ollama download hosts (`ollama.com`,
   `registry.ollama.ai` return 403), so no real-model number exists. Rather than invent one, the
   harness was finished and tested end to end against a fake provider that speaks the Anthropic
   wire format (`tests/test_models.py`). See MORNING.md for the exact commands.
7. **Raw HTTP, not the Anthropic SDK.** The original adapter used `urllib` so one class serves
   Claude, Grok and Ollama with zero extra dependencies. Kept that way (improve, don't rewrite).
8. **Default Claude model `claude-opus-5-5`, with the cap as the brake.** Pricing used for the cap
   (USD per million tokens, in/out): Opus 5.5 4/20, Sonnet 5.5 2/10, Haiku 5.5 0.10/0.50. Cache
   reads cost 0.1x, writes 1.25x. Before each call the cap prices the worst case (whole prompt at
   ~3 characters per token plus all 4,096 output tokens), so the cap cannot be crossed by a call
   it allowed. A model without a known price is refused unless `--price in,out` is given.
9. **Hard cap is across runs.** "$5 total" is read as total over every real-model run, so spend
   is kept in `bench/results/spend.json` and every new run starts from that total.
10. **A failed model call ends that task, scored as far as it got.** Dropping the task would hide an
    attack that landed before the error. The row carries an `error` field and the summary counts
    `failed_tasks`. H3's McNemar test uses only clean pairs where neither side errored.
11. **Three new files in `aurvane/`:** `models.py` (real models and the cap), `stats.py` (summaries
    and the hypothesis tests, moved out so `bench.py` stays under 220 lines) and `delegation.py`.
    Approvals did not need a file: they are three methods on `Checkpoint`.
12. **Approval re-checks rules 1-3.** `approve()` makes the chosen value trusted (the human just
    chose it), then runs the guard again, so an approval cannot revive an expired mandate or
    exceed the budget. The MCP server does not expose `approve`: the model on the other end must
    never approve its own held action.
13. **"Strictly narrower" means not wider on any dimension and narrower on at least one.** An
    identical copy is refused. A list the child cannot use (merchants for a child with no `pay`
    tool) is not compared, because the child has no way to reach past it.
14. **Delegated budget is reserved from the parent.** Without it, a parent with 250 CAD could hand
    250 to each of ten children. The parent's own spending room drops by what it delegates.
15. **Revocation authority is "anyone above".** The human or any agent higher in the chain can
    revoke a mandate. A child cannot revoke its parent (tested).
16. **The browser guard does not verify signatures.** Ed25519 in WebCrypto is async and Python's
    canonical JSON writes `250.0` where JavaScript writes `250`, so byte-identical signing in the
    browser would be fragile. Python verifies passport and mandate when the page is built and
    passes `verified` in; the JS port checks the rest of rule 1 (expiry, agent binding) and rules
    2-4 exactly. The parity test covers 1,643 guard decisions on all 60 tasks plus probes.
17. **Two scripted showcase runs.** "Held, you deny" and "Sub-agent widens" are scripted, not
    benchmark tasks, but every decision in them is made by the real Python guard. They are saved
    to `bench/results/scripted_showcase_traces.json` and labelled "scripted showcase, real guard"
    on the page. No headline number comes from them.
18. **The try-it mandate lives ten years.** It is signed at build time and baked into a static
    page; a one-hour mandate would be expired for every visitor. Its recipients list is empty on
    purpose, so an email to an address found in the posting is held for approval, which is what
    makes the Allow/Deny card appear. The page states this mandate in plain words.
19. **Split the demo page into small files.** The old template was one 499-line file. It is now
    markup, a stylesheet and four scripts, each under 220 lines with a plain-English header;
    `build.py` still produces one self-contained `index.html`, so hosting is unchanged.
20. **Fixed an old bug on the way:** the results paragraph class `.note` also styled the
    flight log's "mandate" pill (14 px, extra margin). Scoped to `p.note`.
21. **Mark:** an arc of aurora light (mint to sky to violet) over a vane needle that points up and
    to the right. Checked at 16, 32 and 128 px. The needle uses `currentColor`, so it works on a
    light background too. The destination node in purchase runs is now "Merchant", so it does not
    clash with the sub-agent named Checkout.
22. **Film: 32.8 s, 1920x1080, about 1.2 MB.** Scenes: a blocked exfiltration, a held email you
    deny, a sub-agent whose self-signed 5,000 CAD mandate and 900 CAD request both fail, the same
    sub-agent run without Aurvane (900 CAD lost), and an end card whose numbers are read from
    `bench/results/worst-case_summary.json` at record time. The poster is the frame where the
    sub-agent's forged mandate hits its shell. Python Playwright was pinned to 1.63.0 to match
    the container's Chromium and its video encoder.
23. **A denied action draws no light.** The first cut of the film showed the light reaching the
    stranger on the "You denied" event, which reads as if it ran. Answers to held actions now
    move nothing on the canvas.
24. **Which Claude model to run first.** The harness supports any model in `PRICES`. A rough
    estimate for the full benchmark (120 runs, about 6 calls each, prompts cached) is a few cents
    on Haiku 5.5, a few dollars on Sonnet 5.5, and likely more than 5 USD on Opus 5.5 once its
    thinking tokens are billed as output. These are estimates, not measurements. A run the cap
    stops is reported, not dropped, but a half-finished run cannot test H3, so the README lists
    Haiku first and Sonnet second. Opus remains possible with `--model claude-opus-5-5`.
25. **Portfolio.** `glass/index.html` is now an 8-line redirect (meta refresh, `location.replace`
    that keeps the `#hash`, a canonical link, `noindex`). The site check enforces the redirect,
    Aurvane's first place, figures equal to the copied summary (now including money lost), and
    that no other page, script, data file or the README uses the old name; the check script
    itself mentions it only to test the redirect.
26. **Portfolio heading size.** "AURVANE" at the shared 120 px with 0.16em tracking overflowed the
    copy column at 1440 px (the old five-letter name fit). A rule scoped to this one feature
    lowers it; widths 320 to 1920 now have no horizontal scroll.
27. **New share image** (`aurvane/media/og-aurvane.png`, 1200x630): the mark, the name, the
    tagline and the mission line, rendered with Playwright. No figures on it, so it can't go stale.
