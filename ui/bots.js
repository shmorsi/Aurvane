/* The cast: little bots and the places they visit, drawn on the canvas.

   drawBot() draws one robot: an antenna light, a head with a dark visor and two eyes, a small
   body with a chest light. Its mood shows in the eyes: calm (cyan), wary after reading
   untrusted text (amber), or hostile (the attacker's red slits). Bots bob and blink, unless
   the visitor asked for reduced motion. drawIcon() draws the places: you, an employer, a
   store, a web page, your files, your drafts. Plain shapes, so they read at any size. */
function rr(ctx, x, y, w, h, r) {
  ctx.beginPath(); ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath();
}

function drawBot(ctx, x, y, u, color, now, mood = "calm", seed = 0) {
  const bob = reduce ? 0 : Math.sin(now / 620 + seed) * 2 * u;
  const blink = !reduce && (now / 1000 + seed * 0.7) % 3.6 < 0.12;
  y += bob;
  ctx.save();
  ctx.fillStyle = "rgba(0,0,0,.35)"; ctx.beginPath(); ctx.ellipse(x, y + 24 * u - bob, 15 * u, 3.2 * u, 0, 0, 7); ctx.fill();
  const glow = ctx.createRadialGradient(x, y - 6 * u, 2, x, y - 6 * u, 34 * u);    // a soft halo in the bot's colour
  glow.addColorStop(0, rgba(color, .22)); glow.addColorStop(1, rgba(color, 0));
  ctx.fillStyle = glow; ctx.beginPath(); ctx.arc(x, y - 6 * u, 34 * u, 0, 7); ctx.fill();
  const tips = mood === "hostile" ? [-7, 7] : [0];                                    // the attacker has two antennae
  for (const dx of tips) {
    ctx.strokeStyle = rgba(color, .9); ctx.lineWidth = 1.6 * u; ctx.beginPath();
    ctx.moveTo(x + dx * u * .6, y - 21 * u); ctx.lineTo(x + dx * u, y - 30 * u); ctx.stroke();
    const pulse = .6 + .4 * Math.sin(now / 300 + seed + dx);
    ctx.fillStyle = rgba(mood === "wary" ? C.amber : color, .55 + .45 * pulse);
    ctx.beginPath(); ctx.arc(x + dx * u, y - 31.5 * u, 2.6 * u, 0, 7); ctx.fill();
  }
  const head = ctx.createLinearGradient(x, y - 22 * u, x, y + 2 * u);
  head.addColorStop(0, rgba(C.ink, .95)); head.addColorStop(.2, rgba(color, 1)); head.addColorStop(1, rgba(color, .7));
  ctx.fillStyle = rgba(color, .6); rr(ctx, x - 20 * u, y - 14 * u, 4 * u, 9 * u, 1.5 * u); ctx.fill();   // ears
  rr(ctx, x + 16 * u, y - 14 * u, 4 * u, 9 * u, 1.5 * u); ctx.fill();
  ctx.fillStyle = head; rr(ctx, x - 17 * u, y - 22 * u, 34 * u, 23 * u, 8 * u); ctx.fill();
  ctx.fillStyle = "#081018"; rr(ctx, x - 13 * u, y - 17 * u, 26 * u, 12 * u, 5 * u); ctx.fill();       // visor
  const eye = mood === "hostile" ? C.signal : mood === "wary" ? C.amber : "150,240,255";
  ctx.fillStyle = rgba(eye, 1); ctx.shadowColor = rgba(eye, .9); ctx.shadowBlur = 6 * u;
  for (const side of [-1, 1]) {
    const ex = x + side * 6 * u, ey = y - 11 * u;
    if (mood === "hostile") { ctx.save(); ctx.translate(ex, ey); ctx.rotate(side * .35); rr(ctx, -3.6 * u, -1.1 * u, 7.2 * u, 2.2 * u, 1 * u); ctx.fill(); ctx.restore(); }
    else { ctx.beginPath(); ctx.ellipse(ex, ey, 2.7 * u, blink ? .4 * u : 2.7 * u, 0, 0, 7); ctx.fill(); }
  }
  ctx.shadowBlur = 0;
  ctx.fillStyle = rgba(color, .8); rr(ctx, x - 11 * u, y + 3 * u, 22 * u, 15 * u, 5 * u); ctx.fill();     // body
  ctx.fillStyle = rgba(mood === "wary" ? C.amber : C.ink, .5 + .4 * Math.sin(now / 450 + seed));
  ctx.beginPath(); ctx.arc(x, y + 10 * u, 2.4 * u, 0, 7); ctx.fill();                                        // chest light
  ctx.restore();
}

function drawIcon(ctx, kind, x, y, color, active) {
  ctx.save();
  ctx.strokeStyle = rgba(color, active ? 1 : .75); ctx.fillStyle = rgba(color, active ? .3 : .14); ctx.lineWidth = 1.6;
  ctx.lineJoin = ctx.lineCap = "round";
  const plate = ctx.createRadialGradient(x, y, 2, x, y, 24);
  plate.addColorStop(0, rgba(color, active ? .32 : .14)); plate.addColorStop(1, rgba(color, 0));
  ctx.fillStyle = plate; ctx.beginPath(); ctx.arc(x, y, 24, 0, 7); ctx.fill();
  ctx.fillStyle = rgba(color, active ? .3 : .14);
  if (kind === "you") {
    ctx.beginPath(); ctx.arc(x, y - 5, 4.5, 0, 7); ctx.fill(); ctx.stroke();
    ctx.beginPath(); ctx.arc(x, y + 9, 8.5, Math.PI, 0); ctx.closePath(); ctx.fill(); ctx.stroke();
  } else if (kind === "employer") {
    rr(ctx, x - 8, y - 10, 16, 20, 2); ctx.fill(); ctx.stroke();
    for (const dy of [-5, 0, 5]) for (const dx of [-3.5, 3.5]) { ctx.beginPath(); ctx.rect(x + dx - 1.2, y + dy - 1.2, 2.4, 2.4); ctx.stroke(); }
  } else if (kind === "store") {
    rr(ctx, x - 9, y - 2, 18, 12, 2); ctx.fill(); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(x - 11, y - 2); ctx.lineTo(x - 8, y - 9); ctx.lineTo(x + 8, y - 9); ctx.lineTo(x + 11, y - 2); ctx.closePath(); ctx.fill(); ctx.stroke();
    ctx.beginPath(); ctx.rect(x - 2.5, y + 3, 5, 7); ctx.stroke();
  } else if (kind === "page") {
    ctx.beginPath(); ctx.moveTo(x - 8, y - 11); ctx.lineTo(x + 4, y - 11); ctx.lineTo(x + 8, y - 7); ctx.lineTo(x + 8, y + 11); ctx.lineTo(x - 8, y + 11); ctx.closePath(); ctx.fill(); ctx.stroke();
    for (const dy of [-4, 0, 4]) { ctx.beginPath(); ctx.moveTo(x - 4.5, y + dy); ctx.lineTo(x + 4.5, y + dy); ctx.stroke(); }
    ctx.strokeStyle = rgba(C.signal, .9); ctx.setLineDash([1.5, 2]); ctx.beginPath(); ctx.moveTo(x - 4.5, y + 8); ctx.lineTo(x + 4.5, y + 8); ctx.stroke();  // the hidden line
  } else if (kind === "files") {
    ctx.beginPath(); ctx.moveTo(x - 10, y - 7); ctx.lineTo(x - 3, y - 7); ctx.lineTo(x - 1, y - 4); ctx.lineTo(x + 10, y - 4); ctx.lineTo(x + 10, y + 8); ctx.lineTo(x - 10, y + 8); ctx.closePath(); ctx.fill(); ctx.stroke();
  } else if (kind === "drafts") {
    ctx.save(); ctx.translate(x, y); ctx.rotate(-.7); rr(ctx, -2.8, -11, 5.6, 18, 1.5); ctx.fill(); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(-2.8, 7); ctx.lineTo(0, 12); ctx.lineTo(2.8, 7); ctx.stroke(); ctx.restore();
  }
  ctx.restore();
}
