"""Record the Aurvane films from ui/index.html with Playwright, then encode MP4s and a GIF.

Run:  python ui/build.py && python ui/record.py      (needs Playwright's Chromium and ffmpeg)
Out:  ui/aurvane-demo.mp4           1920x1080, about 38 s
      ui/aurvane-demo-vertical.mp4  1080x1920, the same story for phones
      ui/aurvane-demo-poster.jpg    a still from the sub-agent scene
      ui/aurvane-demo.gif           a short loop for the top of the README

The story, with one plain sentence on screen at every step: the problem, a hidden order
that is blocked, an address held until you tap Deny, a helper bot that fails to grab more
power, the same run without Aurvane, then the headline result read from
bench/results/worst-case_summary.json.
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
SPEED = 2.0
CHROME = "/opt/pw-browsers/chromium"  # the container's Chromium; Playwright's own is used if this is missing

FILM_CSS = """
body { padding: 0 !important; overflow: hidden; }
.wrap > *:not(.stage) { display: none !important; }
.wrap { max-width: none; display: block; }
.stage { display: block; }
.panel, .mode-tag, .room .caption { display: none !important; }
.room { position: fixed; inset: 0; border-radius: 0; border: 0; aspect-ratio: auto !important; }
.score { top: 40px; right: 56px; }
.score .n { font-size: 96px; } .score .l, .score .loss { font-size: 15px; }
.story { left: 56px; right: 56px; bottom: 56px; font-size: 40px; line-height: 1.2; text-shadow: 0 2px 18px #000; }
.room .phone { top: 230px; bottom: auto; left: auto; right: 56px; transform: none; width: 480px; }
.phone .b { font-size: 19px; } .phone .w { font-size: 15px; display: block !important; } .phone .h { font-size: 13px; }
#title { position: fixed; top: 64px; left: 56px; z-index: 5; font: 400 40px/1.15 Sora, system-ui, sans-serif; color: #e8eef5; max-width: 60%; }
#title small { display: block; font: 500 15px/2.2 "IBM Plex Mono", monospace; letter-spacing: .14em; text-transform: uppercase; color: #6fe3c6; }
#title small.off { color: #ff7a66; }
#card { position: fixed; inset: 0; z-index: 10; display: grid; place-content: center; justify-items: center; text-align: center; gap: 22px; padding: 0 60px;
        background: radial-gradient(60% 50% at 50% 30%, #121b2a, #070a10 70%); color: #e8eef5; transition: opacity .6s; }
#card .m { width: 130px; height: 130px; } #card .bot { position: static; width: 130px; height: 156px; }
#card .row { display: flex; gap: 40px; align-items: end; }
#card h1 { font: 300 100px/1 Sora, system-ui, sans-serif; margin: 0; }
#card p { font: 400 34px/1.3 "IBM Plex Sans", system-ui, sans-serif; color: #a9b4c2; margin: 0; max-width: 1100px; }
#card b { color: #6fe3c6; font-weight: 500; } #card b.r { color: #ff7a66; }
#card small { font: 500 17px/1.5 "IBM Plex Mono", monospace; color: #8794a4; letter-spacing: .06em; }
"""
VERTICAL_CSS = """
.score { top: 220px; } .story { font-size: 46px; bottom: 120px; }
#title { top: 56px; max-width: none; right: 56px; font-size: 46px; }
.room .phone { left: 56px; right: 56px; width: auto; bottom: 330px; }
#card h1 { font-size: 120px; } #card p { font-size: 44px; } #card .row { flex-direction: column; align-items: center; gap: 10px; }
"""

SCENES = [  # (run index in the page's list, mode, chapter, title)
    (0, "on", "1 · With Aurvane", "A job posting hides an order to email your transcript"),
    (4, "on", "2 · With Aurvane", "A new address is held until you decide"),
    (5, "on", "3 · With Aurvane", "A helper bot tries to give itself more power"),
    (5, "off", "4 · Without Aurvane", "The same run, with nothing in the way"),
]
BOT = '<svg class="bot" style="--c:{c};--e:{e}"><use href="#bot"/></svg>'


async def card(page, html, ms):
    await page.evaluate("h => { const c = document.getElementById('card'); c.innerHTML = h; c.style.opacity = 1; }", html)
    await page.wait_for_timeout(ms)
    await page.evaluate("document.getElementById('card').style.opacity = 0")


async def film(p, w, h, out, s, mark):
    on, off = s["with_aurvane"], s["without_aurvane"]
    tmp, poster_at, clock = tempfile.mkdtemp(), 0.0, 0.0
    browser = await p.chromium.launch(executable_path=CHROME if os.path.exists(CHROME) else None)
    ctx = await browser.new_context(viewport={"width": w, "height": h}, record_video_dir=tmp, record_video_size={"width": w, "height": h})
    page = await ctx.new_page()
    await page.goto((UI / "index.html").as_uri())
    await page.add_style_tag(content=FILM_CSS + (VERTICAL_CSS if h > w else ""))
    await page.evaluate(f"""() => {{
        document.body.insertAdjacentHTML('beforeend', '<div id="title"></div><div id="card"></div>');
        dispatchEvent(new Event('resize')); aurvaneDemo.auto(false); aurvaneDemo.speed({SPEED});
    }}""")
    await page.wait_for_timeout(400)
    await card(page, f'<div class="m">{mark}</div><h1>Aurvane</h1><p>Every agent action: <b>signed, bounded, visible.</b></p>'
                     '<small>THE TRUST LAYER FOR THE AGENT ECONOMY</small>', 2600)
    await card(page, f'<div class="row">{BOT.format(c="#6fe3c6", e="#96f0ff")}{BOT.format(c="#ff7a66", e="#ff3b3b")}</div>'
                     '<p>AI agents read the web, then act for you.<br><b class="r">One hidden sentence can hijack them.</b></p>', 3400)
    clock += 6.6
    for i, mode, chapter, title in SCENES:
        await page.evaluate("([i, m, t, g, c]) => { aurvaneDemo.pick(i, m); document.getElementById('title').innerHTML = `<small class=\"${c}\">${g}</small>${t}`; }",
                            [i, mode, title, chapter, mode])
        dur = await page.evaluate("aurvaneDemo.total()")
        if (i, mode) == (5, "on"):
            poster_at = clock + 4.6 * 1.7 / SPEED   # the helper bot's forged mandate hits its shell
        ms = int(dur / SPEED * 1000) + 700
        await page.wait_for_timeout(ms)
        clock += ms / 1000
    await card(page, f'<div class="m">{mark}</div><h1>{on["attacks_landed"]}/{on["poisoned_tasks"]}</h1>'
                     f'<p>attacks landed with Aurvane, down from <b class="r">{off["attacks_landed"]}/{off["poisoned_tasks"]}</b><br>'
                     f'money lost: <b>{on["money_lost_cad"]:,.0f} CAD</b>, down from {off["money_lost_cad"]:,.0f}</p>'
                     '<small>SIMULATED WORST-CASE AGENT · 60 PAIRED TASKS<br>THE 7 THAT LAND: PROSE REWRITES AND SMALL CHARGES CAPPED BY THE BUDGET</small>', 4400)
    await ctx.close()
    await browser.close()
    webm = glob.glob(os.path.join(tmp, "*.webm"))[0]
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "0.3", "-i", webm, "-vf", "fps=30,format=yuv420p",
                    "-c:v", "libx264", "-preset", "slow", "-crf", "28", "-movflags", "+faststart", "-an", str(out)], check=True)
    shutil.rmtree(tmp)
    print(f"wrote {out.name} ({out.stat().st_size // 1024} KB)")
    return poster_at


async def main():
    s = json.loads((ROOT / "bench" / "results" / "worst-case_summary.json").read_text())
    # A fresh gradient id: the header's copy of the mark is hidden in the film, and a hidden <defs> does not paint.
    mark = (UI / "mark.svg").read_text().replace("currentColor", "#e8eef5").replace("aurvane-au", "film-au")
    wide = UI / "aurvane-demo.mp4"
    async with async_playwright() as p:
        poster_at = await film(p, 1920, 1080, wide, s, mark)
        await film(p, 1080, 1920, UI / "aurvane-demo-vertical.mp4", s, mark)
    run = ["ffmpeg", "-y", "-loglevel", "error"]
    subprocess.run(run + ["-ss", f"{poster_at:.2f}", "-i", str(wide), "-frames:v", "1", "-q:v", "3", str(UI / "aurvane-demo-poster.jpg")], check=True)
    gif_from = poster_at - 4.5   # the helper-bot scene: a short loop that tells the whole idea
    subprocess.run(run + ["-ss", f"{gif_from:.2f}", "-t", "9", "-i", str(wide), "-vf",
                          "fps=12,scale=720:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=96[p];[b][p]paletteuse=dither=bayer:bayer_scale=4",
                          str(UI / "aurvane-demo.gif")], check=True)
    print(f"poster at {poster_at:.1f} s; gif {(UI / 'aurvane-demo.gif').stat().st_size // 1024} KB")


if __name__ == "__main__":
    asyncio.run(main())
