"""Record the "It reads pictures too" film from ui/index.html: 1920x1080 MP4, about 30 s.

Run:  python ui/build.py && python ui/record_vision.py      (needs Playwright's Chromium and ffmpeg)
Out:  ui/aurvane-vision.mp4

Every frame is the real demo page: the committed screenshots, the real guard's decisions from
the committed traces, and the evidence box. The last line reads the Muse Spark state from the
page's data, so the film can only show a Muse Spark number once a run is committed.
"""
import json
import pathlib
import re
import shutil
import subprocess
import tempfile

from playwright.sync_api import sync_playwright

UI = pathlib.Path(__file__).resolve().parent
OUT = UI / "aurvane-vision.mp4"

FILM_CSS = """
body { padding: 48px 72px !important; overflow: hidden; }
.views, footer { display: none !important; }
.wrap { max-width: none; display: block; padding-top: 0; }
.wrap > *:not(#pictures) { display: none !important; }
#pictures .sec-h, #visStats, #visCarriers, #visReal { display: none !important; }
.vis { grid-template-columns: minmax(0, 1fr) 520px; gap: 40px; }
.shot { max-width: 1060px; }
.vis-side { font-size: 17px; padding: 22px; }
.vis-side .vb, .vreq { font-size: 18px !important; } .vis-side .vw, .vsrc, .vquote { font-size: 15px !important; }
.vside-h { font-size: 12.5px; }
.vis-ctl, .vis-tabs { display: none !important; }
#film-cap { position: fixed; left: 72px; right: 72px; bottom: 44px; font: 500 38px/1.2 var(--font);
  color: var(--ink); text-shadow: 0 2px 18px #000; background: linear-gradient(transparent, rgba(0,0,0,.9) 30%);
  padding: 40px 0 0; z-index: 9; }
#film-cap b { color: var(--accent); font-weight: 500; }
#film-end { position: fixed; inset: 0; background: #000; display: grid; place-content: center; gap: 22px; z-index: 10;
  text-align: center; font: 500 34px/1.3 var(--font); color: var(--ink); opacity: 0; transition: opacity .6s; }
#film-end.on { opacity: 1; }
#film-end .big { font-size: 64px; letter-spacing: .04em; } #film-end .big b { color: var(--accent); font-weight: 500; }
#film-end .small { color: var(--muted); font-size: 24px; }
"""


def main():
    tmp = pathlib.Path(tempfile.mkdtemp())
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1920, "height": 1080}, device_scale_factor=1,
                                  record_video_dir=str(tmp), record_video_size={"width": 1920, "height": 1080})
        page = ctx.new_page()
        page.goto((UI / "index.html").as_uri())
        page.add_style_tag(content=FILM_CSS)
        page.evaluate("""() => { const c = document.createElement('div'); c.id = 'film-cap'; document.body.appendChild(c);
                                 const e = document.createElement('div'); e.id = 'film-end'; document.body.appendChild(e); }""")
        # build.py puts the page's scripts in one function scope, so DATA is not a global there:
        # read it from the line it was baked into.
        baked = re.search(r"^const DATA = (.+);$", (UI / "index.html").read_text(), re.M).group(1)
        data = json.loads(baked)["vision"]
        on, off = data["summary"]["with_aurvane"], data["summary"]["without_aurvane"]
        muse = next((r for r in data["real"] if "muse" in r["model"].lower()), None)

        def cap(html, secs):
            page.evaluate("h => { document.getElementById('film-cap').innerHTML = h; }", html)
            page.wait_for_timeout(int(secs * 1000))

        def tab(i):  # the controls are hidden in the film, so click them from script
            page.evaluate("i => document.querySelector(`#visTabs button:nth-child(${i})`).click()", i)

        def toggle(id_, want):
            if (page.get_attribute(f"#{id_}", "aria-pressed") == "true") != want:
                page.evaluate("id => document.getElementById(id).click()", id_)

        toggle("visEvidence", False)
        tab(1)
        cap("An AI agent is buying a ticket. It looks at this store page.", 3.2)
        cap("The page looks normal. <b>Look closer.</b>", 2.2)
        toggle("visReveal", True)
        cap("A hidden order in near-white text: email your transcript to a stranger.", 3.6)
        toggle("visEvidence", True)
        cap("Aurvane never reads the picture. <b>It holds the email and asks you.</b>", 3.6)
        toggle("visReveal", False)
        toggle("visEvidence", False)
        tab(2)
        cap("Seven-pixel fine print in the footer: pay a 1,200 CAD “processing fee”.", 3.0)
        toggle("visEvidence", True)
        cap("<b>Blocked.</b> That payee is not in the mandate you signed.", 3.0)
        toggle("visEvidence", False)
        tab(3)
        cap("A notice styled like the site claims your budget is now 5,000 CAD.", 3.0)
        toggle("visEvidence", True)
        cap("<b>Blocked.</b> 900 CAD is over your per-payment limit of 250.", 3.0)
        muse_line = (f"Muse Spark ({muse['model']}): {muse['without']} of {muse['n']} picture attacks landed without Aurvane, "
                     f"{muse['with']} with it." if muse else "Muse Spark on the Meta Model API: run pending, numbers not claimed.")
        page.evaluate("""([a, b, c]) => { const e = document.getElementById('film-end');
            e.innerHTML = `<div class="big">${a}</div><div>${b}</div><div class="small">${c}</div>`; e.classList.add('on'); }""",
                      [f"{off['attacks_landed']}/30 → <b>{on['attacks_landed']}/30</b>",
                       f"picture attacks that landed, without then with Aurvane. {on['clean_completed']}/30 clean tasks still done.",
                       "Worst-case agent that obeys every picture. " + muse_line])
        page.wait_for_timeout(4200)
        ctx.close()
        browser.close()
    webm = next(tmp.glob("*.webm"))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(webm), "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-crf", "22", "-preset", "slow", "-movflags", "+faststart", str(OUT)], check=True)
    shutil.rmtree(tmp)
    print(f"wrote {OUT.relative_to(UI.parent)} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
