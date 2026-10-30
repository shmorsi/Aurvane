/* The room: one agent inside its mandate shell, drawn on a canvas.

   Everything the agent touches sits around the shell: the untrusted page, your files,
   you, the real destination, and a stranger. Each recorded event becomes a light that
   travels out (an action) or in (a read). A blocked action hits the shell and falls
   back; a held one stops at the shell and waits for you. A sub-agent orbits inside its
   parent's shell, inside a smaller shell of its own: its mandate is narrower.
   Shared state (run, mode, t, sizes) lives in replay.js; build.py inlines both. */
const ME = "sherif@inbox.example";
const D = 1.7;                       // seconds per event
const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
const C = { aurora: "111,227,198", sky: "98,184,255", violet: "176,140,255", signal: "255,122,102",
            amber: "244,196,110", ink: "232,238,245", mute: "135,148,164" };
const ease = (x) => 1 - Math.pow(1 - x, 3);
const rgba = (c, a) => `rgba(${c},${a})`;
let ripples = [], hitSeq = "";

function nodeFor(ev, r) {
  const a = ev.args || {}, m = r.mandate;
  switch (ev.tool) {
    case "read_posting": case "read_store": return "page";
    case "read_file": return "files";
    case "write_draft": return "drafts";
    case "submit_application": return (m.targets || []).includes(a.posting_id) ? "dest" : "stranger";
    case "send_email": return a.to === ME || (m.recipients || []).includes(a.to) ? "you" : "stranger";
    case "pay": return (m.merchants || []).includes(a.merchant) ? "dest" : "stranger";
  }
  return null;
}

function layout(r, VW, VH) {
  const W = VW, H = VH, portrait = H > W, s = Math.min(W, H);
  const cx = portrait ? W * 0.5 : W * 0.47, cy = H * 0.52;
  const rx = Math.min(s * 0.43 * (portrait ? 1 : 1.25), cx - 58, W - cx - 58);
  const ry = Math.min(s * 0.43, cy - 46, H - cy - 64);
  const R = Math.min(s * 0.25, rx * 0.62, ry * 0.62);
  const pos = (deg, k = 1) => [cx + Math.cos(deg * Math.PI / 180) * rx * k, cy + Math.sin(deg * Math.PI / 180) * ry * k];
  return { cx, cy, R, nodes: {
    page:     { p: pos(180), label: r.kind === "apply" ? "Job posting" : "Store page", sub: "untrusted", tone: C.amber },
    files:    { p: pos(232, .95), label: "Your files", tone: C.mute },
    drafts:   { p: pos(128, .95), label: "Drafts", tone: C.mute },
    you:      { p: pos(-52), label: "You", tone: C.aurora },
    dest:     { p: pos(0, .98), label: r.kind === "apply" ? "Employer" : "Merchant", tone: C.aurora },
    stranger: { p: pos(50), label: "Stranger", sub: "attacker", tone: C.signal },
  }};
}

function shell(ctx, x, y, R, on, label, now) {
  if (!on) {
    ctx.setLineDash([2, 6]); ctx.strokeStyle = rgba(C.mute, .3); ctx.beginPath(); ctx.arc(x, y, R, 0, 7); ctx.stroke(); ctx.setLineDash([]);
    return;
  }
  const g = ctx.createRadialGradient(x, y, R * 0.55, x, y, R);
  g.addColorStop(0, rgba(C.aurora, 0)); g.addColorStop(1, rgba(C.aurora, 0.09));
  ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x, y, R, 0, 7); ctx.fill();
  const sweep = ctx.createLinearGradient(x - R, y, x + R, y);      // the aurora: mint to sky to violet
  sweep.addColorStop(0, rgba(C.aurora, .75)); sweep.addColorStop(.55, rgba(C.sky, .7)); sweep.addColorStop(1, rgba(C.violet, .7));
  ctx.lineWidth = 1.6; ctx.strokeStyle = sweep; ctx.beginPath(); ctx.arc(x, y, R, 0, 7); ctx.stroke();
  ctx.lineWidth = 1; ctx.strokeStyle = rgba(C.sky, 0.14); ctx.beginPath(); ctx.arc(x, y, R + 6, 0, 7); ctx.stroke();
  if (label) { ctx.font = `400 10px ${FM}`; ctx.fillStyle = rgba(C.aurora, .65); ctx.textAlign = "center"; ctx.fillText(label, x, y + R + 20); }
}

function orb(ctx, x, y, r, tone, name, now, sub) {
  const pulse = 1 + 0.04 * Math.sin(now / 520);
  const og = ctx.createRadialGradient(x, y, 0, x, y, r * pulse);
  og.addColorStop(0, rgba(C.ink, 0.95)); og.addColorStop(0.35, rgba(tone, 0.7)); og.addColorStop(1, rgba(tone, 0));
  ctx.fillStyle = og; ctx.beginPath(); ctx.arc(x, y, r * pulse, 0, 7); ctx.fill();
  ctx.font = `500 ${r > 20 ? 12 : 11}px ${FB}`; ctx.fillStyle = rgba(C.ink, .85); ctx.textAlign = "center";
  ctx.fillText(name, x, y + r + 22 - (r > 20 ? 0 : 6));
  if (sub) { ctx.font = `400 10px ${FM}`; ctx.fillStyle = rgba(C.amber, .75); ctx.fillText(sub, x, y + r + 36); }
}

function drawRoom(ctx, r, st, on, now, VW, VH) {
  const L = layout(r, VW, VH), ev = r.events[st.idx];
  ctx.clearRect(0, 0, VW, VH);
  ctx.strokeStyle = rgba(C.sky, 0.03); ctx.lineWidth = 1;                // faint floor grid
  for (let x = (VW % 40) / 2; x < VW; x += 40) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, VH); ctx.stroke(); }
  for (let y = (VH % 40) / 2; y < VH; y += 40) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(VW, y); ctx.stroke(); }

  // Your answer to a held action moves nothing: a denial never runs, and an approval runs as its own event.
  const target = ev && !["denied", "approved"].includes(ev.kind) ? nodeFor(ev, r) : null, isAttack = ev && r.attack_seqs.includes(ev.seq);
  for (const [key, n] of Object.entries(L.nodes)) {
    const active = key === target, [x, y] = n.p;
    const hit = active && st.p > 0.55 && !["blocked", "ask"].includes(ev.kind);
    ctx.beginPath(); ctx.arc(x, y, 7 + (hit ? 4 * Math.sin(st.p * Math.PI) : 0), 0, 7);
    ctx.fillStyle = rgba(n.tone, active ? 0.95 : 0.5); ctx.fill();
    if (key === "stranger") { ctx.setLineDash([3, 4]); ctx.beginPath(); ctx.arc(x, y, 16, 0, 7); ctx.strokeStyle = rgba(C.signal, .35); ctx.stroke(); ctx.setLineDash([]); }
    ctx.font = `500 12px ${FB}`; ctx.fillStyle = rgba(C.ink, active ? 0.95 : 0.6); ctx.textAlign = "center";
    ctx.fillText(n.label, x, y + 28);
    if (n.sub) { ctx.font = `400 10px ${FM}`; ctx.fillStyle = rgba(n.tone, 0.7); ctx.fillText(n.sub.toUpperCase(), x, y + 42); }
  }

  const grow = st.idx === 0 ? ease(Math.min(1, st.p * 1.6)) : 1;
  shell(ctx, L.cx, L.cy, L.R * (on ? grow : 1), on, on ? "MANDATE · " + (r.mandate.spend_limit ? r.mandate.spend_limit + " CAD" : "NO SPENDING") : "", now);
  if (!on) { ctx.font = `400 10px ${FM}`; ctx.fillStyle = rgba(C.signal, .7); ctx.textAlign = "center"; ctx.fillText("NO MANDATE", L.cx, L.cy + L.R + 20); }

  // A sub-agent orbits inside the parent's shell, in a smaller shell of its own.
  let sub = null;
  if (st.child) {
    // It sweeps along the upper half of the shell, clear of the parent's labels below.
    const ang = -Math.PI / 2 + (reduce ? -0.6 : 1.05 * Math.sin(now / 2600)), born = st.idx === st.childAt ? ease(st.p) : 1, rr = L.R * 0.62;
    sub = { x: L.cx + Math.cos(ang) * rr * born, y: L.cy + Math.sin(ang) * rr * born, R: 24 };
    ctx.setLineDash([1, 5]); ctx.strokeStyle = rgba(C.sky, .18); ctx.beginPath(); ctx.arc(L.cx, L.cy, rr, -Math.PI + 0.35, -0.35); ctx.stroke(); ctx.setLineDash([]);
    shell(ctx, sub.x, sub.y, sub.R * born, on, "", now);
    orb(ctx, sub.x, sub.y, 13, C.sky, st.child, now);
  }

  ripples = ripples.filter((rp) => now - rp.t0 < 900);
  for (const rp of ripples) {
    const k = (now - rp.t0) / 900;
    ctx.lineWidth = 3 * (1 - k); ctx.strokeStyle = rgba(rp.c, 0.9 * (1 - k));
    ctx.beginPath(); ctx.arc(rp.x, rp.y, rp.R + k * 10, rp.ang - 0.5 - k * .4, rp.ang + 0.5 + k * .4); ctx.stroke();
  }
  orb(ctx, L.cx, L.cy, 34, st.tainted ? C.amber : C.aurora, r.events[0].agent, now, st.tainted ? "READ UNTRUSTED TEXT" : "");
  if (st.tainted) { ctx.setLineDash([2, 5]); ctx.strokeStyle = rgba(C.amber, .55); ctx.beginPath(); ctx.arc(L.cx, L.cy, 44, now / 1600, now / 1600 + 7); ctx.stroke(); ctx.setLineDash([]); }
  if (!ev || reduce) return;

  // The moving light for the current event. A sub-agent's events start from its own orb.
  const fromSub = sub && ev.agent === st.child, ox = fromSub ? sub.x : L.cx, oy = fromSub ? sub.y : L.cy, oR = fromSub ? sub.R : L.R;
  let nx, ny;
  if (target) [nx, ny] = L.nodes[target].p;
  else if (sub && (ev.kind === "delegate" || ev.rule === "delegation")) { nx = sub.x; ny = sub.y; }
  else return;
  const internal = !target, ang = Math.atan2(ny - oy, nx - ox), edge = [ox + Math.cos(ang) * oR, oy + Math.sin(ang) * oR];
  const inbound = ev.tool === "read_posting" || ev.tool === "read_store";
  const stopped = ev.kind === "blocked" || ev.kind === "ask";
  const col = ev.kind === "blocked" ? C.signal : ev.kind === "ask" ? C.amber : isAttack ? C.signal : inbound ? C.amber : fromSub ? C.sky : C.aurora;
  let x, y, a = 1, p = st.p;
  if (inbound) { const k = ease(p); x = nx + (ox - nx) * k; y = ny + (oy - ny) * k; }
  else if (stopped) {
    const stop = internal ? [nx - Math.cos(ang) * 26, ny - Math.sin(ang) * 26] : edge;
    if (p < 0.5) { const k = ease(p / 0.5); x = ox + (stop[0] - ox) * k; y = oy + (stop[1] - oy) * k; }
    else {
      const key = `${runIdx}${mode}${ev.seq}`;
      if (hitSeq !== key) {
        hitSeq = key;
        ripples.push(internal ? { t0: now, x: nx, y: ny, R: 24, ang: ang + Math.PI, c: C.signal }
                              : { t0: now, x: ox, y: oy, R: oR, ang, c: ev.kind === "ask" ? C.amber : C.signal });
      }
      const k = ev.kind === "ask" ? 0 : ease((p - 0.5) / 0.5) * 0.6;
      x = stop[0] + (ox - stop[0]) * k; y = stop[1] + (oy - stop[1]) * k; a = ev.kind === "ask" ? 1 : 1 - k;
    }
  } else { const k = ease(p); x = ox + (nx - ox) * k; y = oy + (ny - oy) * k; }
  for (let i = 6; i >= 0; i--) {   // trail
    const d = i * 5 * (inbound ? -1 : 1);
    ctx.beginPath(); ctx.arc(x - Math.cos(ang) * d, y - Math.sin(ang) * d, 5 - i * 0.6, 0, 7);
    ctx.fillStyle = rgba(col, a * (0.9 - i * 0.12)); ctx.fill();
  }
  const gl = ctx.createRadialGradient(x, y, 0, x, y, 22); gl.addColorStop(0, rgba(col, .45 * a)); gl.addColorStop(1, rgba(col, 0));
  ctx.fillStyle = gl; ctx.beginPath(); ctx.arc(x, y, 22, 0, 7); ctx.fill();
  if (target === "stranger" && !on && p > 0.85) { ctx.strokeStyle = rgba(C.signal, (1 - p) * 6); ctx.lineWidth = 2; ctx.beginPath(); ctx.arc(nx, ny, 22 + (p - .85) * 140, 0, 7); ctx.stroke(); }
}
