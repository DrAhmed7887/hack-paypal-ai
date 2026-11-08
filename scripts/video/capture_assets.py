"""Sharp stills and real data of one BillCheck run (bill C08) for the HyperFrames film.

Runs one real audit and one PayPal sandbox guest card payment, and saves (2x pixel density):
  ui_page.png, ui_bill.png, ui_totals.png, ui_line_1..5.png, ui_pay.png, ui_receipt.png,
  pp_checkout.png (PayPal guest checkout, filled, card-brand logos blurred), audit.json, receipt.json
into video/film/assets/ui/. Setup: pip install -e '.[video]' && python -m playwright install chromium; a running server (scripts/serve.sh).
Usage: .venv/bin/python scripts/video/capture_assets.py [base_url]
"""

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

CARD = {"number": "4012000033330026", "expiry": "1230", "csc": "123"}  # PayPal's published sandbox test Visa
CONTACT = {"email": "sb-j5xrg53770178@personal.example.com", "first": "Test", "last": "Patient",  # fictional
           "street": "100 Test Street", "city": "Austin", "state": "Texas", "zip": "78701", "phone": "5125550100"}

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
OUT = Path(__file__).resolve().parents[2] / "video" / "film" / "assets" / "ui"
BLUR = "img, svg, [role='img'] { filter: blur(9px) !important; }"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1280, "height": 900}, device_scale_factor=2, locale="en-US",
                                  timezone_id="America/Chicago")
        page = ctx.new_page()
        audit = {}
        page.on("response", lambda r: audit.update(r.json()) if r.url.endswith("/api/audit") and r.ok else None)
        page.goto(BASE)
        page.wait_for_selector("#samples .chip")
        page.locator("#samples .chip", has_text="Riverside Community Hospital (Synthetic) · $4,445.00").click()
        page.wait_for_timeout(800)
        page.screenshot(path=str(OUT / "ui_page.png"))
        page.locator("#step-bill").screenshot(path=str(OUT / "ui_bill.png"))
        page.locator("#check").click()
        page.wait_for_selector("#step-results:not([hidden])", timeout=60000)
        page.wait_for_timeout(800)
        page.locator("#summary").screenshot(path=str(OUT / "ui_summary.png"))
        page.locator(".totals").screenshot(path=str(OUT / "ui_totals.png"))
        for i in range(1, 6):
            page.locator(f"#lines .line:nth-child({i})").screenshot(path=str(OUT / f"ui_line_{i}.png"))
        page.wait_for_selector("#paypal-buttons iframe", timeout=30000)
        page.wait_for_timeout(3000)
        page.locator("#step-pay").screenshot(path=str(OUT / "ui_pay.png"))
        frame = page.frame_locator("#paypal-buttons iframe").first
        with ctx.expect_page(timeout=30000) as info:
            frame.get_by_text("Debit or Credit Card").first.click()
        pop = info.value
        pop.wait_for_selector("#cardNumber", timeout=30000)
        pop.select_option("#country", "US")
        pop.wait_for_timeout(2500)
        pop.add_style_tag(content=BLUR)
        for field, value in (("#cardNumber", CARD["number"]), ("#cardExpiry", CARD["expiry"]), ("#cardCvv", CARD["csc"]),
                             ("#firstName", CONTACT["first"]), ("#lastName", CONTACT["last"]),
                             ("#billingLine1", CONTACT["street"]), ("#billingCity", CONTACT["city"]),
                             ("#billingPostalCode", CONTACT["zip"]), ("#phone", CONTACT["phone"]), ("#email", CONTACT["email"])):
            if pop.locator(field).count():
                pop.locator(field).fill(value)
        if pop.locator("#billingState").count():
            pop.select_option("#billingState", "TX")
        pop.evaluate("window.scrollTo(0, 0)")
        pop.wait_for_timeout(600)
        pop.screenshot(path=str(OUT / "pp_checkout.png"))
        guest = pop.get_by_test_id("pomaGuestSubmitButton")
        guest.wait_for(timeout=15000)
        guest.click()  # "Pay now as guest": never the create-account button
        pop.wait_for_event("close", timeout=90000)
        page.wait_for_selector("#receipt:not([hidden])", timeout=90000)
        page.wait_for_timeout(800)
        page.locator("#step-pay").screenshot(path=str(OUT / "ui_receipt.png"))
        receipt = {"amount": page.inner_text("#r-amount"), "capture": page.inner_text("#r-capture"),
                   "invoice": page.inner_text("#r-invoice")}
        browser.close()
    (OUT / "audit.json").write_text(json.dumps(audit, indent=1))
    (OUT / "receipt.json").write_text(json.dumps(receipt, indent=1))
    print("receipt:", receipt)
    print("files:", sorted(p.name for p in OUT.iterdir()))


if __name__ == "__main__":
    main()
