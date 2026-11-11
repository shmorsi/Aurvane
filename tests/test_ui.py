"""The two demo pages that ui/build.py bakes stay in step, and the one for the portfolio stays a page of it.

ui/index.html is self-contained. ui/site/index.html is served at shmorsi.github.io/aurvane/: it
loads that site's stylesheet and script, so it must not bring a palette of its own, and nothing in
the demo may collide with that site's class names. A build signs fresh keys, so the pages cannot
be compared byte for byte; these tests check what must hold in any build.
"""
import collections
import json
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
UI = ROOT / "ui"
SOLO, SITE = UI / "index.html", UI / "site" / "index.html"
SECTIONS = ["how", "room", "recorder", "try", "pictures", "results", "red-team", "rules", "limits", "next"]
# Ids the scripts fill in: every one must be on both pages.
FILLED = ["roomBox", "cv", "score", "story", "runs", "log", "chain", "steps", "hidden", "chips", "visTabs", "visShot",
          "visStats", "visCarriers", "stats", "bars", "redteam", "redteamSum", "realModels"]
# Class names that mean something else in the portfolio's stylesheet or script. The demo must not use them.
RESERVED = {"hero", "hero-copy", "story", "stage", "step", "rules", "seg", "lab", "phone", "attack", "wrap", "mark", "eyebrow", "lede", "zero", "ch", "open"}


def markup(path):
    """The page without its inlined style, script and data."""
    text = path.read_text()
    text = re.sub(r"<style>.*?</style>", "", text, flags=re.S)
    return re.sub(r"<script>.*?</script>", "", text, flags=re.S)


@pytest.fixture(scope="module")
def pages():
    assert SOLO.is_file() and SITE.is_file(), "run `python ui/build.py`"
    return {"solo": markup(SOLO), "site": markup(SITE)}


@pytest.mark.parametrize("which", ["solo", "site"])
def test_every_section_and_every_filled_element_is_there_once(pages, which):
    ids = collections.Counter(re.findall(r'\bid="([^"]+)"', pages[which]))
    assert [i for i, n in ids.items() if n > 1] == []
    for sid in SECTIONS + FILLED:
        assert ids[sid] == 1, f"{which} page is missing #{sid}"


def test_both_pages_show_the_same_demo(pages):
    piece = re.compile(r'<div class="room" id="roomBox">.*?<div class="transport">.*?</div>', re.S)
    assert piece.search(pages["solo"]).group(0) == piece.search(pages["site"]).group(0)
    head = lambda text: re.findall(r"<h2 id=\"[\w-]+\">(.*?)</h2>", text)  # noqa: E731
    assert len(head(pages["solo"])) == len(head(pages["site"])) == len(SECTIONS)


def test_the_site_page_is_a_page_of_the_portfolio(pages):
    site, raw = pages["site"], SITE.read_text()
    for needed in ('href="../assets/site.css"', 'src="../assets/site.js"', '<header class="site-header">', '<footer class="site-footer">',
                   '<header class="cs-hero wrap', "data-subnav", 'class="project-switch"', 'data-metrics="../data/projects.json"'):
        assert needed in raw, needed
    # The section index of that site is built from these headings.
    assert re.findall(r'<section class="cs-section" id="([\w-]+)" aria-labelledby="s-[\w-]+">\s*<h2 id="s-[\w-]+">', site) == SECTIONS
    # Its colours and type come from the site's stylesheet: no palette of its own, in any spelling.
    style = "".join(re.findall(r"<style>(.*?)</style>", raw, flags=re.S))
    for token in ("--bg:", "--ink:", "--accent:", "--surface:", "--font:", "--void", "--aurora", "--signal", "--amber", "--pane", "@font-face"):
        outside_room = re.sub(r":where\(\.av\) \.room \{.*?\}", "", style, flags=re.S)   # the room is a dark screen in both themes
        assert token not in outside_room, f"the site page defines {token}; it must use the portfolio's tokens"


def test_the_site_page_quotes_the_committed_results():
    s = json.loads((ROOT / "bench" / "results" / "worst-case_summary.json").read_text())
    on, off = s["with_aurvane"], s["without_aurvane"]
    text = markup(SITE)
    assert (f"attacks that landed fell from {off['attacks_landed']} of {off['poisoned_tasks']} to "
            f"{on['attacks_landed']} of {on['poisoned_tasks']}") in text
    assert f"{off['money_lost_cad']:,.0f} CAD to {on['money_lost_cad']:,.0f} CAD" in text
    rt = json.loads((ROOT / "bench" / "results" / "redteam_summary.json").read_text())
    assert f"{rt['contained']} contained, {rt['capped']} capped by the budget, {rt['gets through']} get through" in text


def test_component_styles_are_scoped_and_use_no_reserved_class():
    css = re.sub(r"/\*.*?\*/", "", (UI / "style.css").read_text(), flags=re.S)
    css = re.sub(r"@media[^{]+\{", "", css)
    used = set(re.findall(r"\.([a-zA-Z][\w-]*)", re.sub(r"\{[^}]*\}", "{}", css)))
    flat = re.sub(r":is\([^()]*\)", ":is()", css)                 # a list inside :is() is one selector
    selectors = [s.strip() for block in re.findall(r"([^{}]+)\{[^{}]*\}", flat) for s in block.split(",")]
    loose = [s for s in selectors if s and not s.startswith((":where(.av)", ":root[data-theme=\"light\"] :where(.av)"))]
    assert loose == [], f"selectors outside the .av scope: {loose[:5]}"
    for name in ("parts.html", "replay.js", "tryit.js", "vision.js"):
        for attr in re.findall(r'class(?:Name)?\s*=\s*["`\']([^"`\']*)["`\']', (UI / name).read_text()):
            used |= {c for c in re.split(r"\s+", re.sub(r"\$\{[^}]*\}", " ", attr)) if re.fullmatch(r"[a-zA-Z][\w-]*", c)}
    for call in re.findall(r'el\("(?:div|span|p|button)",\s*"([^"]+)"', (UI / "tryit.js").read_text()):
        used |= set(call.split())
    assert used & RESERVED == set(), f"the demo uses class names the portfolio already uses: {sorted(used & RESERVED)}"
