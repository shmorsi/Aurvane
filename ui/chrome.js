// The site header's behaviour, as on the rest of shmorsi.github.io: a menu on small screens, and a
// header that tucks away while the reader scrolls down and returns on the way up.
(() => {
  const button = document.querySelector("[data-menu-button]");
  const nav = document.getElementById("site-nav");
  if (button && nav) {
    const set = (open) => {
      nav.classList.toggle("open", open);
      document.body.classList.toggle("nav-open", open);
      button.setAttribute("aria-expanded", String(open));
      button.textContent = open ? "Close" : "Menu";
      if (open) document.body.classList.remove("tucked");
    };
    button.addEventListener("click", () => set(!nav.classList.contains("open")));
    addEventListener("keydown", (e) => { if (e.key === "Escape") set(false); });
    nav.addEventListener("click", (e) => { if (e.target.closest("a")) set(false); });
  }
  let last = scrollY;
  addEventListener("scroll", () => {
    const y = scrollY;
    if (Math.abs(y - last) < 6) return;
    const open = nav && nav.classList.contains("open");
    document.body.classList.toggle("tucked", !open && y > last && y > 120);
    last = y;
  }, { passive: true });
})();
