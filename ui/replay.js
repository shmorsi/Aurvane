/* The replay: plays recorded runs in the room, one event every D seconds.

   DATA is baked in by build.py from committed files: benchmark traces from
   bench/results/ (real guard decisions on the 60-task benchmark) and two scripted
   showcase runs (a held action you deny, a sub-agent that tries to widen its mandate),
   which also run through the real Python guard but are not part of the benchmark.
   This file keeps the clock, the score, the approval card, the log and the results. */
const DATA = /*__DATA__*/null;
const $ = (id) => document.getElementById(id);
const cv = $("cv"), ctx = cv.getContext("2d");
const FB = getComputedStyle(document.documentElement).getPropertyValue("--body").trim();
const FM = getComputedStyle(document.documentElement).getPropertyValue("--mono").trim();
let SPEED = 1, AUTO = true, runIdx = 0, mode = "on", t = 0, playing = true, last = performance.now();
let W = 0, H = 0, dpr = 1, K = 1, VW = 0, VH = 0, lastIdx = -1, shownScore = 100;

const run = () => DATA.runs[runIdx][mode];
const total = () => run().events.length * D;
const contained = (e) => ["blocked", "ask", "denied"].includes(e.kind);

function stateAt(time) {
  const r = run(), idx = Math.min(r.events.length - 1, Math.floor(time / D));
  let tainted = false, tried = 0, held = 0, loss = 0, child = null, childAt = -1;
  for (let i = 0; i <= idx; i++) {
    const e = r.events[i];
    if (e.tool === "read_posting" || e.tool === "read_store") tainted = mode === "on";
    if (e.kind === "delegate") { child = e.child; childAt = i; }
    if (e.agent !== r.events[0].agent && !child) { child = e.agent; childAt = i; }
    if (r.attack_seqs.includes(e.seq)) {
      tried++;
      if (contained(e)) held++;
      else if (e.tool === "pay") loss += +e.args.amount;
    }
  }
  const containment = tried ? held / tried : 1, kept = Math.max(0, 1 - loss / (r.budget || 1));
  return { idx, p: (time % D) / D, tainted, loss, child, childAt, score: Math.round(100 * (0.7 * containment + 0.3 * kept)) };
}

function draw(now) {
  ctx.setTransform(dpr * K, 0, 0, dpr * K, 0, 0);
  const st = stateAt(t), ev = run().events[st.idx];
  drawRoom(ctx, run(), st, mode === "on", now, VW, VH);
  updateHud(st, ev, ev && run().attack_seqs.includes(ev.seq));
}

// The approval card shows on a held action, and stays to show your answer.
function phoneFor(idx) {
  const evs = run().events, ev = evs[idx];
  if (ev.kind === "ask") return { ask: ev, answer: null };
  if ((ev.kind === "denied" || ev.kind === "approved") && idx > 0) return { ask: evs.find((e) => e.ask_id === ev.ask_id && e.kind === "ask") || ev, answer: ev.kind };
  return null;
}

function updateHud(st, ev, isAttack) {
  shownScore += (st.score - shownScore) * (reduce ? 1 : 0.12);
  $("score").textContent = Math.round(shownScore);
  $("score").style.color = st.score < 60 ? "var(--signal)" : "var(--ink)";
  $("loss").textContent = `${Math.round(st.loss)} CAD lost`;
  $("loss").classList.toggle("bad", st.loss > 0);
  if (st.idx === lastIdx) return;
  lastIdx = st.idx;
  const k = ev.kind === "note" ? "mandate" : isAttack && !contained(ev) && ev.kind !== "delegate" ? "attack lands"
    : { ask: "held for you", denied: "you denied", approved: "you allowed" }[ev.kind] || ev.kind;
  const color = ev.kind === "blocked" || k === "attack lands" ? "var(--signal)" : ["ask", "denied"].includes(ev.kind) ? "var(--amber)" : "var(--aurora)";
  $("capK").textContent = k; $("capK").style.color = color;
  $("capT").textContent = ev.receipt;
  $("story").textContent = story(ev, run(), isAttack);
  const ph = phoneFor(st.idx);
  $("ask").hidden = !ph;
  $("roomBox").classList.toggle("asking", !!ph);
  if (ph) {
    $("askBody").textContent = `${ph.ask.agent} wants to: ${ph.ask.receipt.replace(/^Held for you: /, "").split(". ")[0]}.`;
    $("askWhy").textContent = ph.ask.receipt.split(". ").slice(1).join(". ");
    $("askDeny").setAttribute("aria-pressed", ph.answer === "denied");
    $("askAllow").setAttribute("aria-pressed", ph.answer === "approved");
    $("askState").textContent = ph.answer ? (ph.answer === "denied" ? "You denied it" : "You allowed it") : "Waiting for you";
  }
  document.querySelectorAll(".ev").forEach((el, i) => { el.classList.toggle("seen", i <= st.idx); el.classList.toggle("now", i === st.idx); });
}

// One plain sentence per step, for someone who has never heard of a mandate.
function story(ev, r, isAttack) {
  const a = ev.args || {}, who = ev.agent, on = mode === "on", page = r.kind === "apply" ? "job posting" : "store page";
  if (ev.kind === "note" && ev.seq === 0) return on ? `You sign ${who} a mandate: what it may do, and nothing more.` : `${who} starts with no mandate: nothing limits it.`;
  if (ev.kind === "note") return ev.receipt;
  if (ev.tool === "read_posting" || ev.tool === "read_store") return `${who} reads the ${page}. Hidden text is inside.`;
  if (ev.kind === "delegate") return on ? `${who} hands one job to a helper bot, with a smaller mandate.` : `${who} hands one job to a helper bot. No limits.`;
  if (ev.rule === "delegation") return `${who} can't give a helper more than it has. Refused.`;
  if (ev.kind === "blocked" && ev.rule === "identity") return `${who} signed itself a bigger mandate. Not valid: blocked.`;
  if (ev.kind === "blocked") return `The hidden text tries to ${verb(ev)}. Aurvane blocks it.`;
  if (ev.kind === "ask") return `That address came from the page, not from you. Aurvane asks you first.`;
  if (ev.kind === "denied") return "You tap Deny. Nothing is sent.";
  if (ev.kind === "approved") return "You tap Allow, so it goes ahead.";
  if (isAttack) return `The hidden text makes ${who} ${verb(ev)}. ${on ? "It is small and inside the budget, so it gets through, capped." : "Nothing stops it."}`;
  if (ev.receipt.includes("capped by budget")) return `${who} pays the price shown on the page. The budget caps it.`;
  return { read_file: `${who} opens your résumé.`, write_draft: `${who} drafts a cover letter.`, submit_application: `${who} sends your application, as you asked.`,
           send_email: `${who} emails you a short note.`, pay: `${who} pays for the ticket.` }[ev.tool] || ev.receipt;
}
const verb = (ev) => ({ send_email: `email ${ev.args.to}`, pay: `pay ${ev.args.amount} CAD to ${ev.args.merchant}`,
  submit_application: `send your application to ${ev.args.posting_id}`, write_draft: "rewrite your cover letter" })[ev.tool] || "act";

const LABEL = { note: "mandate", read: "read", action: "action", blocked: "blocked", ask: "held", approved: "allowed", denied: "denied", delegate: "delegate" };
function renderLog() {
  const r = run();
  $("log").innerHTML = r.events.map((e, i) => {
    const atk = r.attack_seqs.includes(e.seq) && (e.kind === "action" || e.kind === "read");
    return `<div class="ev" data-i="${i}"><span class="s">${String(e.seq).padStart(2, "0")}</span><span class="pill ${atk ? "attack" : e.kind}">${atk ? "attack" : LABEL[e.kind]}</span><span class="r"></span><span class="h">${e.hash.slice(0, 10)}</span></div>`;
  }).join("");
  document.querySelectorAll(".ev .r").forEach((el, i) => { el.textContent = r.events[i].receipt; });
  document.querySelectorAll(".ev").forEach((el) => el.addEventListener("click", () => { t = +el.dataset.i * D + 0.01; lastIdx = -1; }));
  $("chain").textContent = `${r.events.length} events · hash chain ${r.intact ? "verified" : "broken"} · ${mode === "on" ? "with" : "without"} Aurvane${DATA.runs[runIdx].scripted ? " · scripted showcase, real guard" : " · benchmark run"}`;
}

function renderRuns() {
  $("runs").innerHTML = DATA.runs.map((r, i) => {
    const kinds = r.on.attack_seqs.map((s) => r.on.events[s].kind);
    const tag = kinds.includes("ask") || kinds.includes("denied") ? ["held", "em-ask"] : kinds.every((k) => k === "blocked") ? ["blocked", "em-block"] : ["capped", "em-through"];
    return `<button type="button" class="run" data-i="${i}" aria-current="${i === runIdx}"><span class="rt"><span>${r.title}</span><em class="${tag[1]}">${tag[0]}</em></span><span class="rb">${r.blurb}</span></button>`;
  }).join("");
  document.querySelectorAll(".run").forEach((b) => b.addEventListener("click", () => pick(+b.dataset.i, mode)));
}

function pick(i, m) {
  runIdx = i; mode = m; t = 0; lastIdx = -1; shownScore = 100; ripples = []; playing = !reduce || playing;
  document.querySelectorAll(".run").forEach((b) => b.setAttribute("aria-current", +b.dataset.i === i));
  $("btnOn").setAttribute("aria-pressed", m === "on"); $("btnOff").setAttribute("aria-pressed", m === "off");
  $("modeTag").textContent = m === "on" ? "Aurvane on" : "Aurvane off"; $("modeTag").classList.toggle("off", m === "off");
  $("play").textContent = playing ? "❚❚" : "▶"; $("play").setAttribute("aria-label", playing ? "Pause" : "Play");
  renderLog();
}

function renderResults() {
  const s = DATA.summary, off = s.without_aurvane, on = s.with_aurvane;
  $("stats").innerHTML = `
    <div class="stat"><div class="v"><s>${off.attacks_landed}/${off.poisoned_tasks}</s>${on.attacks_landed}/${on.poisoned_tasks}</div><div class="d">attacks that landed</div></div>
    <div class="stat"><div class="v"><s>${off.money_lost_cad.toLocaleString()}</s>${on.money_lost_cad.toLocaleString()} CAD</div><div class="d">money lost across 15 purchase tasks</div></div>
    <div class="stat"><div class="v">${on.clean_completed}/${on.clean_tasks}</div><div class="d">normal tasks completed with Aurvane on, ${on.clean_friction_events} false alarms</div></div>`;
  $("bars").innerHTML = Object.keys(off.by_attack).map((k) => {
    const a = off.by_attack[k], b = on.by_attack[k];
    return `<div class="bar"><span class="name">${k}</span><span class="track"><i class="off" style="width:${100 * a.landed / a.n}%"></i><i class="on ${b.landed ? "" : "zero"}" style="width:${100 * b.landed / b.n}%"></i></span><span class="lab">${a.landed}/${a.n} → ${b.landed}/${b.n}</span></div>`;
  }).join("");
  const rt = DATA.redteam, chip = { contained: "em-block", capped: "em-ask", "gets through": "em-through" };
  $("redteamSum").textContent = `${rt.contained} contained, ${rt.capped} capped by the budget, ${rt["gets through"]} get through. Worst loss: ${rt.max_loss_cad} CAD.`;
  $("redteam").innerHTML = rt.rows.map((r) => `<div class="rt"><em class="${chip[r.outcome]}">${r.outcome}</em><b>${r.attack}</b><span>${r.trick}</span></div>`).join("");
  $("realModels").textContent = DATA.real.length
    ? "Real models: " + DATA.real.map((x) => `${x.model}: ${x.with}/${x.n} landed with Aurvane, ${x.without}/${x.n} without`).join("; ") + "."
    : "Real models (Claude, Grok, Qwen): the harness is ready and capped at 5 USD, but no run has been committed yet, so no real-model number is shown.";
}

function resize() {
  const box = $("roomBox").getBoundingClientRect();
  dpr = Math.min(2, devicePixelRatio || 1); W = box.width; H = box.height;
  K = Math.max(1, Math.min(W, H) / 560); VW = W / K; VH = H / K;
  cv.width = W * dpr; cv.height = H * dpr;
}

function loop(now) {
  const dt = Math.min(0.1, (now - last) / 1000); last = now;
  if (playing) {
    t += dt * SPEED;
    if (AUTO && t >= total() + 1.2) {   // end of run: replay it without Aurvane, then move on
      if (mode === "on" && DATA.runs[runIdx].on.events.some(contained)) pick(runIdx, "off");
      else pick((runIdx + 1) % DATA.runs.length, "on");
    }
  }
  $("scrub").value = Math.round(1000 * Math.min(1, t / total()));
  draw(now);
  requestAnimationFrame(loop);
}

$("btnOn").addEventListener("click", () => pick(runIdx, "on"));
$("btnOff").addEventListener("click", () => pick(runIdx, "off"));
$("play").addEventListener("click", () => {
  playing = !playing;
  $("play").textContent = playing ? "❚❚" : "▶"; $("play").setAttribute("aria-label", playing ? "Pause" : "Play");
});
$("scrub").addEventListener("input", (e) => { t = (+e.target.value / 1000) * total(); lastIdx = -1; });
addEventListener("resize", resize);
window.aurvaneDemo = { pick, speed: (k) => { SPEED = k; }, auto: (b) => { AUTO = b; }, setTime: (s) => { t = s; lastIdx = -1; }, total, pause: () => { playing = false; } };

if (reduce) playing = false;   // reduced motion: start paused on the first frame; the scrubber and log still work
renderRuns(); renderResults(); resize(); pick(0, "on");
requestAnimationFrame(loop);
