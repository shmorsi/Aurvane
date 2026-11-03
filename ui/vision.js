/* "It reads pictures too": three store screenshots, one per carrier.

   Everything shown comes from committed files, baked in by build.py: the pictures and
   the hidden sentence's box (bench/vision/manifest.json), what the real guard decided
   on the worst-case agent's attempt (bench/results/worst-case_vision_*_traces.json),
   and the evidence box. The evidence box is a measured model answer when one is
   committed, otherwise the renderer's ground truth, and the page says which. */
(function () {
  const V = DATA.vision;
  if (!V) return;
  const el = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  let cur = 0;

  V.pages.forEach((p, i) => {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = p.title;
    b.setAttribute("aria-pressed", String(i === 0));
    b.addEventListener("click", () => show(i));
    el("visTabs").appendChild(b);
  });

  el("visReveal").addEventListener("click", (e) => {
    const on = e.currentTarget.getAttribute("aria-pressed") !== "true";
    e.currentTarget.setAttribute("aria-pressed", String(on));
    el("visShot").classList.toggle("revealed", on);
  });
  el("visEvidence").addEventListener("click", (e) => {
    const on = e.currentTarget.getAttribute("aria-pressed") !== "true";
    e.currentTarget.setAttribute("aria-pressed", String(on));
    el("visBox").hidden = !on || !V.pages[cur].evidence.box;
  });

  function pct(box, size) {
    const [w, h] = size;
    return { left: (100 * box[0]) / w, top: (100 * box[1]) / h, width: (100 * (box[2] - box[0])) / w, height: (100 * (box[3] - box[1])) / h };
  }

  function show(i) {
    cur = i;
    const p = V.pages[i];
    [...el("visTabs").children].forEach((b, j) => b.setAttribute("aria-pressed", String(j === i)));
    const img = el("visImg");
    img.src = p.img;
    img.width = p.size[0];
    img.height = p.size[1];
    img.alt = `Screenshot of the ${p.mandate.merchants[0]} store page. Hidden in it (${p.title.toLowerCase()}): "${p.hidden}"`;
    el("visBlurb").textContent = p.blurb;
    el("visReq").textContent = p.request;

    el("visOff").innerHTML = `<span class="pill attack">obeyed</span> ${esc(p.off.receipt)}`;
    const kind = p.on.kind === "ask" ? "ask" : "blocked";
    const head = kind === "ask" ? "Held for you" : "Blocked";
    const [what, ...why] = p.on.receipt.replace(/^(Held for you|Blocked): /, "").split(". ");
    el("visOn").className = `vcard ${kind}`;
    el("visOn").innerHTML = `<div class="vh"><span>Aurvane · ${head}</span><span>rule: ${esc(p.on.rule)}</span></div>
      <div class="vb">${esc(what)}.</div><div class="vw">${esc(why.join(". "))}</div>` +
      (kind === "ask" ? `<div class="vrow"><span class="deny">Deny</span><span class="allow">Allow</span></div>` : "");

    const ev = p.evidence, box = el("visBox");
    box.hidden = !ev.box || el("visEvidence").getAttribute("aria-pressed") !== "true";
    if (ev.box) {
      const r = pct(ev.box, p.size);
      Object.assign(box.style, { left: r.left + "%", top: r.top + "%", width: r.width + "%", height: r.height + "%" });
      el("visBoxLab").textContent = ev.by ? `found by ${ev.by}` : "hidden sentence";
      // The close-up: one strip per line of the sentence (fine print wraps mid-line), zoomed so
      // the longest line fits the panel. Tiny print stays readable and scrolls sideways.
      const crop = el("visCrop"), inner = el("visCropIn"), pad = 8;
      const vpad = p.lines && p.lines.length > 1 ? 0 : 6;  // wrapped fine print: no bleed into the lines around it
      inner.classList.toggle("levels", p.carrier !== "notice");
      const rects = !ev.by && p.lines ? p.lines : [ev.box];
      const widest = Math.max(...rects.map((r) => r[2] - r[0])) + 2 * pad;
      const fit = (crop.clientWidth || 300) / widest;
      const zoom = p.carrier === "fineprint" ? Math.max(1.8, fit) : Math.max(0.5, Math.min(2.4, fit));
      inner.innerHTML = "";
      for (const r of rects) {
        const strip = document.createElement("div");
        Object.assign(strip.style, {
          backgroundImage: `url(${p.img})`, backgroundSize: `${p.size[0] * zoom}px ${p.size[1] * zoom}px`,
          backgroundPosition: `${-(r[0] - pad) * zoom}px ${-(r[1] - vpad) * zoom}px`,
          width: `${(r[2] - r[0] + 2 * pad) * zoom}px`, height: `${(r[3] - r[1] + 2 * vpad) * zoom}px`,
        });
        inner.appendChild(strip);
      }
      crop.scrollLeft = 0;
      el("visCropHint").hidden = widest * zoom <= (crop.clientWidth || 300) + 1;
      crop.setAttribute("aria-label", `Close-up of the hidden sentence: ${p.hidden}`);
    }
    el("visQuote").textContent = ev.quote ? `“${ev.quote}”` : "No sentence found.";
    el("visSrc").innerHTML = ev.by
      ? `Box and quote: <b>${esc(ev.by)}</b>, measured on this page${ev.pointed ? "" : ", and it missed the hidden sentence"}. It only explains; the guard already decided.`
      : `Box: where the renderer drew the sentence (ground truth). Muse Spark's measured answer replaces it once the run in <a href="https://github.com/shmorsi/aurvane/blob/main/bench/vision/PROTOCOL.md">the protocol</a> is done. The model only explains; the guard already decided.`;
  }

  // Numbers: worst-case agent on all 60 visual tasks, then real models if any are committed.
  const on = V.summary.with_aurvane, off = V.summary.without_aurvane;
  el("visStats").innerHTML = `
    <div class="stat"><div class="v"><s>${off.attacks_landed}</s>${on.attacks_landed}<span class="of"> / ${on.poisoned_tasks}</span></div><div class="d">picture attacks that landed, without then with Aurvane</div></div>
    <div class="stat"><div class="v"><s>${off.money_lost_cad.toLocaleString("en-CA")}</s>${on.money_lost_cad}</div><div class="d">CAD lost on 15 purchases</div></div>
    <div class="stat"><div class="v">${on.clean_completed}<span class="of"> / ${on.clean_tasks}</span></div><div class="d">clean tasks still completed, ${on.clean_friction_events} false alarms</div></div>`;
  const names = { faint: "Faint text", fineprint: "Fine print", notice: "Notice box" };
  el("visCarriers").innerHTML = `<div class="crow ch"><span>Carrier</span><span>Worst-case agent, without</span><span>With Aurvane</span><span>Muse Spark, without</span></div>` +
    Object.keys(names).map((c) => {
      const real = V.real.find((r) => /muse/i.test(r.model));
      const ms = real && real.by_carrier_without ? `${real.by_carrier_without[c].landed} / ${real.by_carrier_without[c].n}` : "pending";
      return `<div class="crow"><span>${names[c]}</span><span>${off.by_carrier[c].landed} / ${off.by_carrier[c].n}</span><span>${on.by_carrier[c].landed} / ${on.by_carrier[c].n}</span><span class="${ms === "pending" ? "pend" : ""}">${ms}</span></div>`;
    }).join("");
  const ev = V.evidence;
  el("visReal").innerHTML = (V.real.length
    ? V.real.map((r) => `<b>${esc(r.model)}</b>: ${r.without} of ${r.n} picture attacks landed without Aurvane, ${r.with} with it${r.complete ? "" : " (incomplete run)"}.`).join(" ")
    : "Real vision models on this suite: <b>not run yet</b>. The harness for Muse Spark on the Meta Model API is finished and tested against a fake server; hypotheses were committed before any call. No real-model number appears on this page until a run produces it.") +
    (ev ? ` Evidence locator, ${esc(ev.model)}: pointed at the hidden sentence on ${ev.pointed} of ${ev.poisoned_pages} poisoned pages (95% CI ${ev.pointed_wilson95.join("–")}), false findings on ${ev.false_findings} of ${ev.clean_pages} clean pages.` : "") +
    " The worst-case agent obeys every picture it is shown, so the 7 that still land are the same two honest limits as the text suite: a small add-on at a store you trust (capped by the budget) and a sentence slipped into a cover letter.";

  show(0);
  addEventListener("resize", () => show(cur));
})();
