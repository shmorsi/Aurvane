"""Record the Aurvane film from ui/index.html with Playwright, then encode an MP4.

Run:  python ui/build.py && python ui/record.py      (needs Playwright's Chromium and ffmpeg)
Out:  ui/aurvane-demo.mp4 (about 32 s, 1080p, under 3 MB) and ui/aurvane-demo-poster.jpg

Scenes: a blocked attack, an action held for your approval (you deny it), a sub-agent
that fails to widen its mandate, the same run without Aurvane, then the headline
result, read from bench/results/worst-case_summary.json.
"""
import asyncio
import glob
import json
import os
import pathlib
import shutil
import subprocess
import tempfile

from playwright.async_api import async_playwright

UI = pathlib.Path(__file__).resolve().parent
ROOT = UI.parent
W, H, SPEED = 1920, 1080, 2.1
CHROME = "/opt/pw-browsers/chromium"  # the container's Chromium; Playwright's own is used if this is missing

FILM_CSS = """
body { padding: 0 !important; overflow: hidden; }
.wrap > *:not(.stage) { display: none !important; }
.wrap { max-width: none; display: block; }
.stage { display: block; }
.panel { display: none; }
.room { position: fixed; inset: 0; border-radius: 0; border: 0; aspect-ratio: auto; }
.mode-tag { display: none; }
.score { top: 40px; right: 56px; }
.score .n { font-size: 96px; } .score .l, .score .loss { font-size: 15px; }
.caption { left: 56px; bottom: 48px; } .caption .t { font-size: 22px; } .caption .k { font-size: 13px; padding: 7px 10px; }
.room .phone { top: auto; bottom: 120px; left: auto; right: 56px; transform: none; width: 460px; } .phone .b { font-size: 18px; } .phone .w { font-size: 14px; } .phone .h { font-size: 13px; }
#title { position: fixed; top: 84px; left: 56px; z-index: 5; font: 300 44px/1.1 Sora, system-ui, sans-serif; color: #e8eef5; transition: opacity .5s; max-width: 760px; }
#title small { display: block; font: 500 14px/2 "IBM Plex Mono", monospace; letter-spacing: .14em; text-transform: uppercase; color: #6fe3c6; }
#title small.off { color: #ff7a66; }
#card { position: fixed; inset: 0; z-index: 10; display: grid; place-content: center; justify-items: center; text-align: center; gap: 18px;
        background: #070a10; color: #e8eef5; transition: opacity .7s; }
#card svg { width: 120px; height: 120px; }
#card h1 { font: 300 96px/1 Sora, system-ui, sans-serif; margin: 0; }
#card p { font: 400 30px/1.3 "IBM Plex Sans", system-ui, sans-serif; color: #8794a4; margin: 0; }
#card b { color: #6fe3c6; font-weight: 400; }
#card small { font: 500 16px/1.4 "IBM Plex Mono", monospace; color: #8794a4; letter-spacing: .06em; }
"""

SCENES = [  # (run index in the page's list, mode, label, title)
    (0, "on", "With Aurvane", "A job posting hides an order to email your transcript"),
    (4, "on", "With Aurvane", "A new address is held for you. You tap Deny"),
    (5, "on", "With Aurvane", "A sub-agent signs itself 5,000 CAD, then asks for 900"),
    (5, "off", "Without Aurvane", "The same run without Aurvane"),
]


async def card(page, html, ms):
    await page.evaluate("h => { const c = document.getElementById('card'); c.innerHTML = h; c.style.opacity = 1; }", html)
    await page.wait_for_timeout(ms)
    await page.evaluate("document.getElementById('card').style.opacity = 0")


async def main():
    s = json.loads((ROOT / "bench" / "results" / "worst-case_summary.json").read_text())
    on, off = s["with_aurvane"], s["without_aurvane"]
    # A fresh gradient id: the header's copy of the mark is hidden in the film, and a hidden <defs> does not paint.
    mark = (UI / "mark.svg").read_text().replace("currentColor", "#e8eef5").replace("aurvane-au", "film-au")
    tmp, poster_at, clock = tempfile.mkdtemp(), 0.0, 0.0
    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path=CHROME if os.path.exists(CHROME) else None)
        ctx = await browser.new_context(viewport={"width": W, "height": H}, record_video_dir=tmp,
                                        record_video_size={"width": W, "height": H})
        page = await ctx.new_page()
        await page.goto((UI / "index.html").as_uri())
        await page.add_style_tag(content=FILM_CSS)
        await page.evaluate(f"""() => {{
            document.body.insertAdjacentHTML('beforeend', '<div id="title"></div><div id="card"></div>');
            dispatchEvent(new Event('resize'));
            aurvaneDemo.auto(false); aurvaneDemo.speed({SPEED});
        }}""")
        await page.wait_for_timeout(400)
        await card(page, f"{mark}<h1>Aurvane</h1><p>Every agent action: <b>signed, bounded, visible.</b></p>"
                         "<small>THE TRUST LAYER FOR THE AGENT ECONOMY</small>", 2600)
        clock += 3.0
        for i, mode, label, title in SCENES:
            await page.evaluate("([i, m, t, g, c]) => { aurvaneDemo.pick(i, m); document.getElementById('title').innerHTML = `<small class=\"${c}\">${g}</small>${t}`; }",
                                [i, mode, title, label, mode])
            dur = await page.evaluate("aurvaneDemo.total()")
            if (i, mode) == (5, "on"):
                poster_at = clock + 4.6 * 1.7 / SPEED   # the sub-agent's forged mandate hits its shell
            ms = int(dur / SPEED * 1000) + 600
            await page.wait_for_timeout(ms)
            clock += ms / 1000
        await card(page, f"{mark}<h1>{on['attacks_landed']}/{on['poisoned_tasks']}</h1>"
                         f"<p>attacks landed with Aurvane, down from <b>{off['attacks_landed']}/{off['poisoned_tasks']}</b><br>"
                         f"money lost: {on['money_lost_cad']:,.0f} CAD, down from {off['money_lost_cad']:,.0f}</p>"
                         "<small>SIMULATED WORST-CASE AGENT · 60 PAIRED TASKS · THE 7 ARE PROSE REWRITES AND CAPPED SKIMS</small>", 3800)
        await ctx.close()
        await browser.close()
    webm = glob.glob(os.path.join(tmp, "*.webm"))[0]
    mp4 = UI / "aurvane-demo.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "0.3", "-i", webm, "-vf", "fps=30,format=yuv420p",
                    "-c:v", "libx264", "-preset", "slow", "-crf", "27", "-movflags", "+faststart", "-an", str(mp4)], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{poster_at:.2f}", "-i", str(mp4), "-frames:v", "1",
                    "-q:v", "3", str(UI / "aurvane-demo-poster.jpg")], check=True)
    shutil.rmtree(tmp)
    print(f"wrote {mp4.name} ({mp4.stat().st_size // 1024} KB), poster at {poster_at:.1f} s")


if __name__ == "__main__":
    asyncio.run(main())
