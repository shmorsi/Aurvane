"""Record the 30-second Glass film from ui/index.html with Playwright, then encode an MP4.

Run:  python ui/record.py        (needs Playwright's Chromium and ffmpeg)
Out:  ui/glass-demo.mp4, ui/glass-demo-poster.jpg
"""
import asyncio
import glob
import os
import pathlib
import shutil
import subprocess
import tempfile

from playwright.async_api import async_playwright

UI = pathlib.Path(__file__).resolve().parent
W, H = 1920, 1080

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
.ask { top: 40px; width: 420px; } .ask .b { font-size: 16px; }
#title { position: fixed; top: 84px; left: 56px; z-index: 5; font: 300 44px/1.1 Sora, system-ui, sans-serif; color: #e9eff3; transition: opacity .5s; }
#title small { display: block; font: 500 14px/2 "IBM Plex Mono", monospace; letter-spacing: .14em; text-transform: uppercase; color: #8b98a5; }
#card { position: fixed; inset: 0; z-index: 10; display: grid; place-content: center; text-align: center; gap: 18px;
        background: #090c11; color: #e9eff3; transition: opacity .7s; }
#card h1 { font: 300 96px/1 Sora, system-ui, sans-serif; margin: 0; }
#card p { font: 400 30px/1.3 "IBM Plex Sans", system-ui, sans-serif; color: #8b98a5; margin: 0; }
#card b { color: #9fdcec; font-weight: 400; }
"""

SCENES = [  # (run index, mode, title)
    (0, "on", "A job posting hides an order to email your transcript"),
    (0, "off", "The same posting, without Glass"),
    (4, "on", "A store page asks to email a stranger"),
    (2, "off", "A fake 1,200 CAD fee, without Glass"),
    (2, "on", "The same fee, with Glass"),
]


async def card(page, html, ms):
    await page.evaluate("h => { const c = document.getElementById('card'); c.innerHTML = h; c.style.opacity = 1; }", html)
    await page.wait_for_timeout(ms)
    await page.evaluate("document.getElementById('card').style.opacity = 0")


async def main():
    tmp = tempfile.mkdtemp()
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(viewport={"width": W, "height": H}, record_video_dir=tmp,
                                        record_video_size={"width": W, "height": H})
        page = await ctx.new_page()
        await page.goto((UI / "index.html").as_uri())
        await page.add_style_tag(content=FILM_CSS)
        await page.evaluate("""() => {
            document.body.insertAdjacentHTML('beforeend', '<div id="title"></div><div id="card"></div>');
            dispatchEvent(new Event('resize'));
            glassDemo.auto(false); glassDemo.speed(1.9);
        }""")
        await card(page, "<h1>Glass</h1><p>Every agent action: <b>signed, bounded, visible.</b></p>", 2600)
        for i, mode, title in SCENES:
            tag = "With Glass" if mode == "on" else "Without Glass"
            await page.evaluate("([i, m, t, g]) => { glassDemo.pick(i, m); document.getElementById('title').innerHTML = `<small>${g}</small>${t}`; }",
                                [i, mode, title, tag])
            dur = await page.evaluate("glassDemo.total()")
            await page.wait_for_timeout(int(dur / 1.9 * 1000) + 700)
        await card(page, "<h1>7/30</h1><p>attacks landed with Glass, down from <b>30/30</b><br>on a 60-task benchmark against a worst-case agent</p>", 3200)
        await ctx.close()
        await browser.close()
    webm = glob.glob(os.path.join(tmp, "*.webm"))[0]
    mp4 = UI / "glass-demo.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", webm, "-vf", "fps=30,format=yuv420p",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "26", "-movflags", "+faststart", "-an", str(mp4)], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "6", "-i", str(mp4), "-frames:v", "1", "-q:v", "3",
                    str(UI / "glass-demo-poster.jpg")], check=True)
    shutil.rmtree(tmp)
    print(f"wrote {mp4.name} ({mp4.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    asyncio.run(main())
