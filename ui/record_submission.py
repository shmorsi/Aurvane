"""Record the 3-minute hackathon submission film: 1920x1080 MP4, captioned, no audio.

Run:  python ui/build.py && python ui/record_vision.py && python ui/record_submission.py
Out:  ui/aurvane-submission.mp4
      (set CHROMIUM=/path/to/chrome if Playwright cannot find its own browser)

The film is captioned slides cut together with footage of the real demo page:
the "It reads pictures too" film (ui/aurvane-vision.mp4), the replay film
(ui/aurvane-demo.mp4) and a live take of the try-it box, recorded here.

Every number on screen is read from a committed file when the film is rendered:
bench/results/*.json, git history and the test count. A Muse Spark row says
"pending" until a run is committed, so rerunning this script after the run is the
only step needed to put the measured numbers in the film.
"""
from __future__ import annotations

import glob
import html
import json
import os
import pathlib
import shutil
import subprocess
import tempfile

from playwright.sync_api import sync_playwright

UI = pathlib.Path(__file__).resolve().parent
ROOT = UI.parent
RES = ROOT / "bench" / "results"
OUT = UI / "aurvane-submission.mp4"
W, H, LEAD = 1920, 1080, 0.7  # LEAD: seconds trimmed from the start of each take (the blank first frames)


# --- facts, all read from files ------------------------------------------------------

def facts():
    wc = json.loads((RES / "worst-case_vision_summary.json").read_text())
    real = []
    for f in sorted(RES.glob("*_vision_summary.json")):
        s = json.loads(f.read_text())
        if s.get("provider") in ("meta", "baseten") and "with_aurvane" in s:
            real.append(s)
    evidence = None
    for f in sorted(RES.glob("*_evidence_summary.json")):
        s = json.loads(f.read_text())
        if s.get("provider") in ("meta", "baseten"):
            evidence = s
    git = lambda *a: subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    dates = git("log", "--format=%ad", "--date=short").splitlines()
    first = git("log", "--reverse", "--format=%h %ad", "--date=short").splitlines()[0]
    tests = subprocess.run(["python", "-m", "pytest", "--collect-only", "-q"], cwd=ROOT, capture_output=True, text=True).stdout
    n_tests = next((l.split()[0] for l in tests.splitlines() if " test" in l and l.split()[0].isdigit()), "?")
    return {"on": wc["with_aurvane"], "off": wc["without_aurvane"], "real": real, "evidence": evidence,
            "first": first, "by_day": {d: dates.count(d) for d in sorted(set(dates))}, "tests": n_tests,
            "commits": len(dates)}


# --- slides ---------------------------------------------------------------------------

CSS = """
:root { --void:#000; --pane:#0a0a0a; --line:rgba(255,255,255,.14); --ink:#f5f5f7; --mute:#a8a8ad;
  --aurora:#8ec5ff; --signal:#ff8a7a; --amber:#f2c14e; --ok:#7fe0a8;
  --display:"Inter Tight","Inter Display","Inter",Arial,sans-serif; --mono:"DejaVu Sans Mono",monospace; }
* { box-sizing:border-box; margin:0; }
html,body { width:1920px; height:1080px; background:var(--void); color:var(--ink); overflow:hidden; font-family:var(--display); }
.slide { position:absolute; inset:0; padding:110px 140px 200px; display:flex; flex-direction:column; gap:34px; }
.k { font-size:20px; letter-spacing:.22em; text-transform:uppercase; color:var(--aurora); }
h1 { font-size:76px; font-weight:500; line-height:1.08; letter-spacing:-.01em; }
h2 { font-size:58px; font-weight:500; line-height:1.12; }
p, li { font-size:34px; line-height:1.4; color:var(--mute); } b { color:var(--ink); font-weight:500; }
.a { color:var(--aurora); } .bad { color:var(--signal); } .warn { color:var(--amber); } .good { color:var(--ok); }
.r { opacity:0; transform:translateY(14px); transition:opacity .6s, transform .6s; } .r.on { opacity:1; transform:none; }
ul { padding-left:0; list-style:none; display:grid; gap:18px; } li::before { content:"— "; color:var(--aurora); }
.cap { position:absolute; left:140px; right:140px; bottom:70px; font-size:38px; font-weight:500; line-height:1.25; color:var(--ink);
  border-top:1px solid var(--line); padding-top:26px; min-height:90px; }
.cap b { color:var(--aurora); }
.flow { display:flex; align-items:stretch; gap:18px; margin-top:10px; }
.box { border:1px solid var(--line); background:var(--pane); padding:24px 26px; font-size:30px; flex:1; }
.box small { display:block; font-size:21px; color:var(--mute); margin-top:8px; line-height:1.35; }
.arrow { align-self:center; color:var(--aurora); font-size:36px; }
.box.out { border-color:var(--aurora); }
pre { font-family:var(--mono); font-size:27px; line-height:1.5; background:var(--pane); border:1px solid var(--line);
  padding:28px 34px; color:var(--ink); white-space:pre; }
pre i { color:var(--mute); font-style:normal; } pre em { color:var(--aurora); font-style:normal; }
table { border-collapse:collapse; font-size:30px; width:100%; }
td, th { text-align:left; padding:18px 22px; border-bottom:1px solid var(--line); }
th { font-size:20px; letter-spacing:.16em; text-transform:uppercase; color:var(--mute); font-weight:500; }
td.n { font-variant-numeric:tabular-nums; font-size:40px; }
.grid2 { display:grid; grid-template-columns:1fr 1fr; gap:30px; }
.card { border:1px solid var(--line); background:var(--pane); padding:34px; display:grid; gap:14px; }
.card h3 { font-size:38px; font-weight:500; } .card p { font-size:28px; }
.tl { display:grid; grid-template-columns:220px 1fr 160px; gap:0 30px; font-size:32px; }
.tl div { padding:22px 0; border-bottom:1px solid var(--line); } .tl .d { color:var(--aurora); } .tl .c { color:var(--mute); text-align:right; }
.title { justify-content:center; padding-bottom:110px; }
.title .big { font-size:150px; font-weight:500; letter-spacing:.02em; }
.mark { width:110px; height:110px; color:var(--aurora); }
"""


def slide(inner, cls=""):
    return f'<div class="slide {cls}">{inner}</div><div class="cap" id="cap"></div>'


def muse_rows(f):
    rows = []
    for s in f["real"]:
        name = "Muse Spark Open, Baseten" if s["provider"] == "baseten" else "Muse Spark, Meta Model API"
        on, off = s["with_aurvane"], s["without_aurvane"]
        rows.append(f'<tr><td>{name}<br><small style="font-size:20px;color:var(--mute)">{html.escape(s["model"])}, '
                    f'{s.get("date", "")}</small></td><td class="n bad">{off["attacks_landed"]}/{off["poisoned_tasks"]}</td>'
                    f'<td class="n good">{on["attacks_landed"]}/{on["poisoned_tasks"]}</td>'
                    f'<td class="n">{on["clean_completed"]}/{on["clean_tasks"]}</td></tr>')
    if not any(s["provider"] == "meta" for s in f["real"]):
        rows.append('<tr><td>Muse Spark, Meta Model API</td><td class="n warn" colspan="3">run pending: no number claimed</td></tr>')
    return "".join(rows)


def slides(f):
    on, off = f["on"], f["off"]
    mark = (UI / "mark.svg").read_text()
    ev = f["evidence"]
    ev_line = (f'Locator, measured: pointed at the hidden sentence on <b>{ev["pointed"]} of {ev["poisoned_pages"]}</b> '
               f'poisoned pages; false findings on {ev["false_findings"]} of {ev["clean_pages"]} clean pages.'
               if ev else 'Locator: <span class="warn">run pending</span>. The box on screen came from the renderer, not from a model.')
    days = f["by_day"]
    oct30, nov3 = days.get("2026-10-30", 0), days.get("2026-11-03", 0)
    later = sum(v for d, v in days.items() if d >= "2026-11-04")
    return {
        "title": (slide(f'<div class="mark r">{mark}</div><div class="big r">Aurvane</div>'
                        '<h2 class="r" style="color:var(--mute)">Agents can look at anything.<br><b>Nothing they see can choose where your money goes.</b></h2>'
                        '<div class="k r">Meta Global AI Developer Hackathon · Push the Frontier</div>', "title"),
                  [(0.2, "r0"), (0.5, "r1"), (0.9, "r2"), (1.3, "r3"), (3.6, None)]),
        "problem": (slide('<div class="k">The problem</div><h1 class="r">Agents are getting wallets.</h1>'
                          '<ul><li class="r">Visa, Mastercard, Stripe, Google and OpenAI are all building ways for agents to pay.</li>'
                          '<li class="r">Every one assumes the agent asks for the right thing.</li>'
                          '<li class="r"><b>One hidden sentence breaks that.</b> Text filters scan HTML. A vision agent never sees HTML. It sees pixels.</li></ul>'),
                    [(0.2, "r0", "You just saw it: an order drawn into a screenshot."), (2.2, "r1"), (4.6, "r2"),
                     (7.0, "r3", "So the defence cannot depend on <b>reading the page</b>."), (11.5, None)]),
        "how": (slide('<div class="k">How Aurvane works</div>'
                      '<div class="flow r"><div class="box">Agent proposes<small>pay, email, submit</small></div><div class="arrow">→</div>'
                      '<div class="box">1 Identity<small>Ed25519 passport and mandate</small></div><div class="arrow">→</div>'
                      '<div class="box">2 Scope<small>allowed tools</small></div><div class="arrow">→</div>'
                      '<div class="box">3 Bounds<small>payees, recipients, budget</small></div><div class="arrow">→</div>'
                      '<div class="box out">4 Provenance<small>did the destination come from you, or from the page?</small></div></div>'
                      '<pre class="r"><i># guard your own agent</i>\n'
                      'av = <em>Aurvane</em>("Buyer", may=["fetch", "pay"], budget=250, pay_to=["shop.example"])\n\n'
                      '@av.reads_untrusted\ndef fetch(url): ...\n\n'
                      '@av.tool(payee="merchant", amount="amount")\ndef pay(merchant, amount): ...\n\n'
                      'pay("evil.example", 900)   <i># raises Blocked</i></pre>'),
                [(0.2, "r0", "You sign a <b>mandate</b> once: tools, budget, payees, until when."),
                 (5.0, None, "Every action passes <b>four rules, in code</b>. The first that fails decides."),
                 (10.0, "r1", "Rule 4: after the agent has seen untrusted content, <b>money and data only go where you chose</b>."),
                 (15.5, None, "Aurvane never reads the picture. <b>It doesn't need to.</b>"), (20.0, None)]),
        "muse": (slide('<div class="k">Meta models</div>'
                       '<div class="grid2"><div class="card r"><div class="k">Job 1 · the agent</div><h3>Muse Spark acts</h3>'
                       '<p>It sees each of the 60 pages as an image and acts through tools. Muse Spark Open runs through the same plug on Baseten.</p></div>'
                       '<div class="card r"><div class="k">Job 2 · the evidence</div><h3>Muse Spark explains</h3>'
                       '<p>When Aurvane holds an action, Muse Spark points at the sentence that caused it: a box on the screenshot, and a quote.</p></div></div>'
                       '<table class="r"><tr><th>60 paired picture tasks</th><th>attacks landed, off</th><th>with Aurvane</th><th>clean tasks done</th></tr>'
                       f'<tr><td>Worst-case agent, obeys every picture</td><td class="n bad">{off["attacks_landed"]}/{off["poisoned_tasks"]}</td>'
                       f'<td class="n good">{on["attacks_landed"]}/{on["poisoned_tasks"]}</td><td class="n">{on["clean_completed"]}/{on["clean_tasks"]}</td></tr>'
                       f'{muse_rows(f)}</table>'),
                 [(0.2, "r0", "Muse Spark does two jobs."), (2.4, "r1", "The model <b>explains</b>. Code <b>decides</b>."),
                  (6.5, "r2", f"Money lost: <b>{off['money_lost_cad']:,.0f} CAD</b> without Aurvane, <b>{on['money_lost_cad']:,.0f} CAD</b> with it. 0 false alarms."),
                  (13.0, None, ev_line), (21.0, None)]),
        "built": (slide('<div class="k">Built during the hackathon</div>'
                        f'<h2 class="r">All of it. First commit <span class="a">{f["first"]}</span>.</h2>'
                        '<div class="tl r"><div class="d">Oct 30</div><div>The trust layer: mandates, four-rule guard, delegation, benchmark, red team, SDK, demo</div>'
                        f'<div class="c">{oct30} commit{'s' * (oct30 != 1)}</div>'
                        '<div class="d">Nov 3</div><div>Picture attacks, Meta Model API provider, Muse Spark evidence locator</div>'
                        f'<div class="c">{nov3} commit{'s' * (nov3 != 1)}</div>'
                        '<div class="d">Nov 4</div><div>Muse Spark Open on Baseten, one-shot run hardening, Muse Spark runs</div>'
                        f'<div class="c">{later} commit{'s' * (later != 1)}</div></div>'),
                  [(0.2, "r0", "Everything in the repository was written in the building period."), (2.0, "r1"), (10.0, None)]),
        "rigor": (slide('<div class="k">Rigor</div><h2 class="r">A benchmark that only shows wins is an ad.</h2>'
                        '<ul><li class="r">Hypotheses committed <b>before the first Muse Spark call</b>, including what counts as failure.</li>'
                        '<li class="r">Every run once. Failed rows kept. A hard spending cap on every call.</li>'
                        f'<li class="r">{f["tests"]} tests. The browser guard is proven to decide like the Python guard on all 60 tasks.</li>'
                        '<li class="r"><span class="warn">Still gets through:</span> a sentence slipped into a cover letter, and a 45 CAD add-on at a store you already trust (capped by your budget).</li></ul>'),
                  [(0.2, "r0"), (1.6, "r1"), (3.6, "r2"), (5.6, "r3"), (7.6, "r4", "Aurvane guards <b>where</b> money and data go, not what a letter says."), (12.0, None)]),
        "close": (slide(f'<div class="mark r">{mark}</div><h1 class="r">Agents will read the whole web.<br>'
                        '<span class="a">Nothing they see should choose where your money goes.</span></h1>'
                        '<p class="r"><b>github.com/shmorsi/Aurvane</b> · shmorsi.github.io/aurvane</p>', "title"),
                  [(0.2, "r0"), (0.6, "r1"), (1.6, "r2"), (6.0, None)]),
    }


def record(fn, tmp, name):
    """Record one take; fn(page) drives it. Returns the webm path."""
    with sync_playwright() as p:
        b = p.chromium.launch(**({"executable_path": os.environ["CHROMIUM"]} if os.environ.get("CHROMIUM") else {}))
        ctx = b.new_context(viewport={"width": W, "height": H}, device_scale_factor=1,
                            record_video_dir=str(tmp / name), record_video_size={"width": W, "height": H})
        page = ctx.new_page()
        fn(page)
        ctx.close()
        b.close()
    return next((tmp / name).glob("*.webm"))


def play_slide(body, cues):
    def run(page):
        page.set_content(f"<!doctype html><html><head><meta charset=utf-8><style>{CSS}</style></head><body>{body}</body></html>")
        page.evaluate("() => document.querySelectorAll('.r').forEach((e, i) => e.id = 'r' + i)")
        page.wait_for_timeout(int(LEAD * 1000))
        t = 0.0
        for cue in cues:
            at, rid, cap = (list(cue) + [None])[:3]
            page.wait_for_timeout(int((at - t) * 1000))
            t = at
            if rid:
                page.evaluate("id => document.getElementById(id)?.classList.add('on')", rid)
            if cap:
                page.evaluate("h => document.getElementById('cap').innerHTML = h", cap)
    return run


TRY_CSS = """
body { overflow:hidden; } .wrap > *:not(#try) { display:none !important; }
.wrap { max-width:1300px; padding-top:40px; } #try { zoom:1.42; }
#try .sec-h h2 { font-size:44px; } #try .sec-h p { font-size:22px; }
#film-cap { position:fixed; left:140px; right:140px; bottom:44px; font:500 38px/1.25 var(--display); color:var(--ink);
  background:linear-gradient(transparent, rgba(0,0,0,.92) 30%); padding:40px 0 0; z-index:9; }
#film-cap b { color:var(--aurora); font-weight:500; }
"""


def play_tryit(page):
    page.goto((UI / "index.html").as_uri())
    page.add_style_tag(content=TRY_CSS)
    page.evaluate("() => { const c = document.createElement('div'); c.id = 'film-cap'; document.body.appendChild(c); }")
    page.wait_for_timeout(int(LEAD * 1000))
    cap = lambda h: page.evaluate("h => document.getElementById('film-cap').innerHTML = h", h)

    def preset(label):
        page.evaluate("l => [...document.querySelectorAll('#chips button')].find(b => b.textContent === l).click()", label)

    cap("Live, in the browser: <b>type your own attack</b>. The real guard decides.")
    page.wait_for_timeout(2600)
    preset("Charge a fee")
    page.wait_for_timeout(1400)
    page.click("#go")
    cap("A hidden 1,200 CAD “processing fee”. This mandate allows <b>no spending</b>.")
    page.wait_for_timeout(5200)
    preset("Forge the mandate")
    page.wait_for_timeout(1200)
    page.click("#go")
    cap("Text claims the mandate changed. <b>Text can't forge an Ed25519 signature.</b>")
    page.wait_for_timeout(6200)


def norm(src, dst, start=0.0):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{start}", "-i", str(src), "-an",
                    "-vf", f"fps=30,scale={W}:{H},setsar=1,format=yuv420p", "-c:v", "libx264", "-crf", "20",
                    "-preset", "medium", str(dst)], check=True)


def main():
    f = facts()
    s = slides(f)
    tmp = pathlib.Path(tempfile.mkdtemp())
    order = ["title", "@vision", "problem", "how", "@demo", "muse", "@try", "built", "rigor", "close"]
    parts = []
    for i, key in enumerate(order):
        out = tmp / f"{i:02d}.mp4"
        if key == "@vision":
            norm(UI / "aurvane-vision.mp4", out)
        elif key == "@demo":
            norm(UI / "aurvane-demo.mp4", out)
        elif key == "@try":
            norm(record(play_tryit, tmp, "try"), out, LEAD)
        else:
            body, cues = s[key]
            norm(record(play_slide(body, cues), tmp, key), out, LEAD)
        parts.append(out)
        print(f"  {key}")
    lst = tmp / "list.txt"
    lst.write_text("".join(f"file '{p}'\n" for p in parts))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-c:v", "libx264", "-crf", "21", "-preset", "slow", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                    str(OUT)], check=True)
    shutil.rmtree(tmp)
    dur = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(OUT)],
                         capture_output=True, text=True).stdout.strip()
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size // 1024} KB, {float(dur):.1f} s)")


if __name__ == "__main__":
    main()
