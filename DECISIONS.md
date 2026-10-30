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
