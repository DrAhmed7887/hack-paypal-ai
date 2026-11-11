"""Record BillCheck running end to end, frame by frame (port of the hack-clocked teaser recorder).

The page runs in a 960x540 CSS window at device scale 2, so every frame is a sharp 1920x1080 screenshot and the
page's 16 px text shows at ~32 px. Mouse, scrolls and the click ring are stepped one frame at a time at 30 fps.
Waits on the network (the AI reader, PayPal) are captured as they happen and their real length is logged, so the
cut can shorten them and say so on screen.

One continuous session against a running server (scripts/serve.sh or scripts/video/serve_rwthgpt.py):
sample bill C08 -> AI reader -> audit -> PayPal sandbox guest card checkout (PayPal's published sandbox test Visa)
-> capture -> invoice marked paid -> audit history.
Usage: .venv/bin/python scripts/video/record_frames.py [base_url]
Output: video/walkthrough/frames/{main,popup}/NNNNN.jpg and video/walkthrough/frames/marks.json
"""

import json
import shutil
import sys
import time
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

CARD = {"number": "4012000033330026", "expiry": "1230", "csc": "123"}  # PayPal's published sandbox test Visa
CONTACT = {"email": "sb-j5xrg53770178@personal.example.com", "first": "Test", "last": "Patient",  # fictional
           "street": "100 Test Street", "city": "Austin", "zip": "78701", "phone": "5125550100"}
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
OUT = Path(__file__).resolve().parents[2] / "video" / "walkthrough" / "frames"
W, H, DSF, FPS = 960, 540, 2, 30
BLUR = ("img, svg:not(#hf-cursor svg), [role='img'] { filter: blur(9px) !important; }"  # card-brand logos
        " img[alt*='PayPal' i], svg[aria-label*='PayPal' i], [aria-label*='PayPal' i] svg,"
        " [aria-label*='PayPal' i] img { filter: none !important; }")  # PayPal's own mark stays
# PayPal's cookie banner covers the form: press its "Close" button (never "accept").
CLOSE_COOKIES = """() => { for (const b of document.querySelectorAll('button'))
  if (b.innerText.trim() === 'Close' && b.offsetParent) { b.click(); return true; } return false; }"""

CURSOR = """(() => {
  const add = () => {
    if (document.getElementById('hf-cursor')) return;
    const c = document.createElement('div');
    c.id = 'hf-cursor';
    c.innerHTML = '<svg width="22" height="22" viewBox="0 0 24 24"><path d="M4 2 L4 19 L8.5 15 L11.5 22 L14.5 20.7 L11.6 14 L18 14 Z" fill="#111" stroke="#fff" stroke-width="1.5" stroke-linejoin="round"/></svg>';
    c.style.cssText = 'position:fixed;left:0;top:0;z-index:2147483647;pointer-events:none;transform:translate(-99px,-99px)';
    const r = document.createElement('div');
    r.id = 'hf-ring';
    r.style.cssText = 'position:fixed;left:0;top:0;width:30px;height:30px;margin:-15px 0 0 -15px;border-radius:50%;border:2px solid rgb(11,95,87);opacity:0;z-index:2147483646;pointer-events:none';
    document.body.append(r, c);
    window.__cur = (x, y, ring) => {
      c.style.transform = 'translate(' + (x - 3) + 'px,' + (y - 2) + 'px)';
      r.style.left = x + 'px'; r.style.top = y + 'px';
      r.style.opacity = ring > 0 ? String(1 - ring) : '0';
      r.style.transform = 'scale(' + (0.4 + ring * 1.1) + ')';
    };
  };
  if (document.readyState === 'loading') addEventListener('DOMContentLoaded', add); else add();
})();"""


def ease(t: float) -> float:
    return 2 * t * t if t < 0.5 else 1 - (-2 * t + 2) ** 2 / 2


class Shot:
    """Frames of one page. Every call that changes what is on screen writes the frames that show it."""

    def __init__(self, page, folder: Path, x: float = W * 0.8, y: float = H * 0.3):
        self.page, self.dir, self.n, self.x, self.y = page, folder, 0, x, y
        folder.mkdir(parents=True, exist_ok=True)

    def frame(self, ring: float = 0) -> None:
        self.page.evaluate("([x, y, r]) => window.__cur && window.__cur(x, y, r)", [self.x, self.y, ring])
        self.page.screenshot(path=str(self.dir / f"{self.n:05d}.jpg"), type="jpeg", quality=92)
        self.n += 1

    def hold(self, sec: float) -> None:
        for _ in range(round(sec * FPS)):
            self.frame()

    def move(self, x: float, y: float, sec: float = 0.8) -> None:
        x0, y0, n = self.x, self.y, round(sec * FPS)
        for i in range(1, n + 1):
            e = ease(i / n)
            self.x, self.y = x0 + (x - x0) * e, y0 + (y - y0) * e
            self.page.mouse.move(self.x, self.y)
            self.frame()

    def move_to(self, locator, sec: float = 0.8, fx: float = 0.5) -> None:
        b = locator.bounding_box()
        self.move(b["x"] + b["width"] * fx, b["y"] + b["height"] / 2, sec)

    def scroll(self, selector: str, frac: float = 0.1, sec: float = 1.0) -> None:
        start, target = self.page.evaluate(
            """([s, f]) => { const el = document.querySelector(s);
                 return [scrollY, Math.max(0, scrollY + el.getBoundingClientRect().top - innerHeight * f)]; }""",
            [selector, frac])
        n = round(sec * FPS)
        for i in range(1, n + 1):
            self.page.evaluate("y => scrollTo(0, y)", start + (target - start) * ease(i / n))
            self.frame()

    def click(self) -> None:  # a real click at the cursor; the ring plays over the next 0.4 s
        self.page.mouse.down()
        self.page.mouse.up()
        self.ring()

    def ring(self) -> None:
        n = round(0.4 * FPS)
        for i in range(1, n + 1):
            self.frame(i / n)

    def until(self, done, timeout_s: float = 120) -> float:
        """Write frames until done() is true; returns the real seconds it took."""
        t0 = time.monotonic()
        while not done():
            if time.monotonic() - t0 > timeout_s:
                raise TimeoutError("waited too long")
            self.frame()
        return round(time.monotonic() - t0, 1)


def visible(page, selector: str):
    return lambda: page.locator(selector).count() > 0 and page.locator(selector).first.is_visible()


def checkout(pop, ps: Shot, marks: dict) -> None:
    marks["paypal_load_s"] = ps.until(visible(pop, "#cardNumber"), 60)
    marks["popup_form"] = ps.n
    pop.select_option("#country", "US")
    pop.add_style_tag(content=BLUR)
    pop.evaluate(CLOSE_COOKIES)
    ps.hold(0.8)
    for field, value in (("#cardNumber", CARD["number"]), ("#cardExpiry", CARD["expiry"]), ("#cardCvv", CARD["csc"]),
                         ("#firstName", CONTACT["first"]), ("#lastName", CONTACT["last"]),
                         ("#billingLine1", CONTACT["street"]), ("#billingCity", CONTACT["city"]),
                         ("#billingPostalCode", CONTACT["zip"]), ("#phone", CONTACT["phone"]), ("#email", CONTACT["email"])):
        pop.evaluate(CLOSE_COOKIES)
        box = pop.locator(field)
        if not box.count():
            continue
        box.scroll_into_view_if_needed()
        box.click()
        for ch in value:  # one frame per key
            box.press(ch)
            ps.frame()
    if pop.locator("#billingState").count():
        pop.select_option("#billingState", "TX")
    marks["popup_filled"] = ps.n
    guest = pop.get_by_test_id("pomaGuestSubmitButton")
    guest.scroll_into_view_if_needed()
    ps.move_to(guest, 0.7)
    ps.hold(0.4)
    marks["popup_submit"] = ps.n
    guest.click()  # "Pay now as guest": never the create-account button
    ps.ring()
    t0 = time.monotonic()
    try:
        while not pop.is_closed():
            ps.frame()
    except PlaywrightError:
        pass  # the window closed between two frames
    marks["paypal_finish_s"] = round(time.monotonic() - t0, 1)
    marks["popup_end"] = ps.n


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    marks: dict = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": W, "height": H}, device_scale_factor=DSF, locale="en-US",
                                  timezone_id="America/Chicago")
        ctx.add_init_script(CURSOR)
        page = ctx.new_page()
        page.goto(BASE)
        page.wait_for_selector("#samples .chip")
        s = Shot(page, OUT / "main")
        s.hold(1.2)
        marks["start"] = 0

        chip = page.locator("#samples .chip", has_text="Riverside Community Hospital (Synthetic) · $4,445.00")
        s.scroll("#samples", 0.25, 0.8)
        s.move_to(chip, 0.9, 0.3)
        marks["pick"] = s.n
        s.click()
        s.hold(0.6)
        s.scroll("#bill-text", 0.12, 0.9)
        s.hold(2.2)
        s.move_to(page.locator("#check"), 0.8)
        marks["check"] = s.n
        s.click()
        marks["ai_start"] = s.n
        marks["ai_wait_s"] = s.until(visible(page, "#step-results"), 120)
        marks["ai_end"] = s.n

        marks["summary_from"] = s.n
        s.scroll("#summary", 0.06, 1.0)
        marks["summary"] = s.n
        s.hold(5.0)
        s.scroll(".totals", 0.15, 0.8)
        marks["totals"] = s.n
        s.hold(3.0)
        for i in (1, 2):
            sel = f"#lines .line:nth-child({i})"
            marks[f"line{i}_from"] = s.n
            s.scroll(sel, 0.08, 0.9)
            s.move_to(page.locator(sel + " .badge, " + sel).first, 0.6, 0.15)
            marks[f"line{i}"] = s.n
            s.hold(4.0)
        marks["line3_from"] = s.n
        s.scroll("#lines .line:nth-child(3)", 0.08, 1.0)
        marks["line3"] = s.n
        s.hold(3.5)

        marks["pay_from"] = s.n
        s.scroll("#step-pay", 0.08, 1.0)
        marks["pay"] = s.n
        marks["paypal_buttons_s"] = s.until(lambda: page.locator("#paypal-buttons iframe").count() > 0, 30)
        s.hold(1.5)
        card_btn = page.frame_locator("#paypal-buttons iframe").first.get_by_text("Debit or Credit Card").first
        s.move_to(card_btn, 0.8)
        marks["card_click"] = s.n
        with ctx.expect_page(timeout=30000) as info:
            card_btn.click()
        s.ring()
        pop = info.value
        marks["popup_open"] = s.n
        ps = Shot(pop, OUT / "popup", x=40, y=40)
        checkout(pop, ps, marks)

        marks["receipt_wait_s"] = s.until(visible(page, "#receipt"), 120)
        marks["receipt_from"] = s.n
        s.scroll("#receipt", 0.06, 1.0)
        marks["receipt"] = s.n
        s.hold(5.0)
        marks["history_from"] = s.n
        s.scroll("#step-history", 0.04, 1.2)
        marks["history"] = s.n
        s.move(W * 0.62, H * 0.62, 1.0)
        s.hold(1.5)
        # The grid is wider than the 960 px window: scroll it sideways so the Payment column shows.
        grid = ".ag-body-horizontal-scroll-viewport"
        width = page.evaluate("s => { const e = document.querySelector(s); return e ? e.scrollWidth - e.clientWidth : 0; }", grid)
        n = round(1.6 * FPS)
        for i in range(1, n + 1):
            page.evaluate("([s, x]) => { document.querySelector(s).scrollLeft = x; }", [grid, width * ease(i / n)])
            s.frame()
        marks["history_paid"] = s.n
        s.hold(4.5)
        marks["end"] = s.n
        receipt = {k: page.inner_text(f"#r-{k}") for k in ("amount", "capture", "invoice")}
        totals = {k: page.inner_text(f"#t-{k}") for k in ("billed", "suggested", "diff")}
        browser.close()
    (OUT / "marks.json").write_text(json.dumps({"marks": marks, "receipt": receipt, "totals": totals}, indent=1))
    print(json.dumps({"marks": marks, "receipt": receipt, "totals": totals}))


if __name__ == "__main__":
    main()
