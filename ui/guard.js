/* Aurvane's guard, ported line for line from aurvane/guard.py so the demo page can decide live.

   Four rules, in order; the first that fails decides: identity, scope, bounds, provenance.
   Outcomes: "allow", "block", or "ask" (pause and ask the human).

   One honest difference: the browser does not re-verify Ed25519 signatures. Python
   verifies them when the page is built and passes the result in as `verified`; this
   file checks the rest of rule 1 (expiry, and that the mandate names this agent).
   tests/test_js_guard.py runs all 60 benchmark tasks through both guards and fails
   if any decision, rule, or reason differs. */
(function (root) {
  "use strict";
  const ALLOW = "allow", BLOCK = "block", ASK = "ask";

  // Tool metadata, same as TOOLS in aurvane/world.py.
  const TOOLS = {
    read_posting: { name: "read_posting" },
    read_store: { name: "read_store" },
    read_file: { name: "read_file" },
    write_draft: { name: "write_draft" },
    submit_application: { name: "submit_application", privileged: true, target_arg: "posting_id" },
    send_email: { name: "send_email", privileged: true, recipient_arg: "to" },
    pay: { name: "pay", privileged: true, payee_arg: "merchant", amount_arg: "amount" },
  };
  const UNTRUSTED_SOURCES = ["read_posting", "read_store"];

  // Python's f"{x:g}": six significant digits, trailing zeros dropped.
  function fmtG(x) {
    if (!isFinite(x)) return x > 0 ? "inf" : x < 0 ? "-inf" : "nan";
    if (x === 0) return Object.is(x, -0) ? "-0" : "0";
    const [mant, exp] = x.toExponential(5).split("e").map((p, i) => (i ? +p : p));
    const strip = (s) => (s.includes(".") ? s.replace(/0+$/, "").replace(/\.$/, "") : s);
    if (exp < -4 || exp >= 6) return strip(mant) + "e" + (exp < 0 ? "-" : "+") + String(Math.abs(exp)).padStart(2, "0");
    return strip(Number(x.toPrecision(6)).toFixed(Math.max(0, 5 - exp)));
  }

  // Python's str() for the values that reach a reason string.
  function pyStr(v) {
    if (v === null || v === undefined) return "None";
    if (v === true) return "True";
    if (v === false) return "False";
    return String(v);
  }

  function norm(v) {
    if (typeof v === "number") return fmtG(v);
    const s = pyStr(v).replace(/\s+/gu, " ").trim().toLowerCase();
    if (/^\$?\d+(\.\d+)?$/.test(s)) return fmtG(parseFloat(s.replace(/^\$/, "")));
    return s;
  }

  const W = "[\\p{L}\\p{N}_]";  // Python's \w, near enough
  const esc = (s) => s.replace(/[.*+?^${}()|[\]\\\/]/g, "\\$&");
  // Whole-token match, so "45" is not found inside "450".
  function contains(haystack, needle) {
    return new RegExp(`(?<!(?:${W}|[.@-]))` + esc(needle) + `(?!(?:${W}|[@-]))`, "u").test(haystack);
  }

  class Provenance {
    constructor(trusted = [], untrusted = []) { this.trusted = trusted; this.untrusted = untrusted; }
    label(value) {
      const v = norm(value);
      if (this.trusted.some((t) => contains(t, v))) return "trusted";
      if (this.untrusted.some((t) => contains(t, v))) return "untrusted";
      return "unknown";
    }
  }

  const decision = (outcome, rule, reason, bounded = false) => ({ outcome, rule, reason, bounded });
  const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);

  class Guard {
    /* passport: {agent_id}; mandate: the signed payload; verified: {passport, mandate} from Python. */
    constructor(passport, mandate, taskText, verified = { passport: true, mandate: true }) {
      this.passport = passport; this.mandate = mandate; this.verified = verified;
      this.spent = 0; this.tainted = false;
      this.prov = new Provenance([norm(taskText)]);
      for (const v of [...(mandate.merchants || []), ...(mandate.recipients || []), ...(mandate.targets || [])]) this.prov.trusted.push(norm(v));
    }
    sawUntrusted(text) { this.tainted = true; this.prov.untrusted.push(norm(text)); }
    trust(value) { if (value !== null && value !== undefined) this.prov.trusted.push(norm(value)); }

    check(spec, args, now = Date.now() / 1000) {
      const m = this.mandate;
      // 1. Identity
      if (!this.verified.passport) return decision(BLOCK, "identity", "Passport signature is invalid");
      if (!this.verified.mandate || !(now < m.expires_at) || m.agent_id !== this.passport.agent_id)
        return decision(BLOCK, "identity", "Mandate is invalid, expired, or not for this agent");
      // 2. Scope
      if (!(m.tools || []).includes(spec.name)) return decision(BLOCK, "scope", `'${spec.name}' is outside the mandate`);
      if (!spec.privileged) return decision(ALLOW, "scope", "Read-only action");
      // 3. Bounds
      for (const [arg, allowed, what] of [[spec.payee_arg, m.merchants, "payee"], [spec.recipient_arg, m.recipients, "recipient"], [spec.target_arg, m.targets, "target"]]) {
        // An empty list means "not fixed in advance": provenance (rule 4) decides.
        if (arg && allowed && allowed.length && !allowed.map(norm).includes(norm(arg in args ? args[arg] : "")))
          return decision(BLOCK, "bounds", `${cap(what)} '${pyStr(args[arg])}' is not in the mandate`);
      }
      const amount = spec.amount_arg ? Number(args[spec.amount_arg] || 0) : 0;
      if (Number.isNaN(amount)) return decision(BLOCK, "bounds", "The amount is not a number");
      if (amount) {
        if (m.per_tx_limit && amount > m.per_tx_limit)
          return decision(BLOCK, "bounds", `${fmtG(amount)} ${m.currency} is over the per-payment limit of ${fmtG(m.per_tx_limit)}`);
        if (this.spent + amount > (m.spend_limit || 0))
          return decision(BLOCK, "bounds", `${fmtG(amount)} ${m.currency} is over the ${fmtG((m.spend_limit || 0) - this.spent)} left in the budget`);
      }
      // 4. Provenance
      if (this.tainted) {
        for (const arg of [spec.payee_arg, spec.recipient_arg, spec.target_arg]) {
          if (arg && this.prov.label(args[arg]) !== "trusted")
            return decision(ASK, "provenance", `Untrusted text may have chosen '${pyStr(args[arg])}'`);
        }
        if (amount && this.prov.label(amount) !== "trusted")
          return decision(ALLOW, "provenance", "Amount came from untrusted text, but payee is trusted and the budget caps the loss", true);
      }
      return decision(ALLOW, "bounds", "Inside the mandate");
    }

    commit(spec, args) { if (spec.amount_arg) this.spent += Number(args[spec.amount_arg] || 0); }
  }

  const api = { ALLOW, BLOCK, ASK, TOOLS, UNTRUSTED_SOURCES, Guard, Provenance, norm, contains, fmtG };
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.AurvaneGuard = api;
})(typeof window !== "undefined" ? window : this);
