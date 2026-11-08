# REVIEW: BillCheck film, storyline A (Studio preview stage, no render)

## Pass 2 (8 Nov): one voice take, music, polish
- **Voice:** the ten single-line clips were replaced by one continuous take, `narration_take.mp3`, at 0.3 s. Every beat is re-anchored to the new line starts and words (table in SPEC.md). Scenes now run bill 0–21.6 s, audit 21.6–57.4 s, pay 57.4–67.15 s, invoice 67.15–80.35 s and close 80.35–94.0 s. The voice ends at 84.91 s; the end card holds to 94.0 s.
- **Music:** a HeyGen catalog track, `bed.wav` (track id ae669990…, "soft modern electronic, warm pads, light pulse, building to hopeful groove", 82 s). I picked it over two others: a 30 s piano loop that was too short, and a 38 s underscore whose build was too slow.
  - **Placement:** it starts at 1.3 s, so section E lands on the PayPal zoom-through (59.8 s) and section F on the capture (67.9 s).
  - **Level:** ducked to 0.14 under the voice, and up to 0.42 in the two payoff pauses.
  - **Tail:** a bar-aligned clip from 6 bars earlier carries the end card, with a 1.5 s fade.
- **Polish:**
  - The ED hero card is now 660 px tall and the CT card 640 px, with a 120 px two-row equation (frame fill 61%, was 45%).
  - The sum: the total is 220 px, the amounts stack at 1.2x, and ui_totals is at 1.1x.
  - The receipt and invoice are 1600 px wide with 40 px rows (the invoice now spans 110–970 px).
  - At the lift (11.85 s) the page recedes from 0.75x to 0.68x and blurs behind a ground-coloured scrim, so the rows sit clearly in front.
  - The labs and injection rows now return from the right, instead of repeating the drop entrance.
- **Fixed warnings:** a dead stretch at 25.9–29.0 s (the RAND label now lands on "private plans"); the typed injection explanation, the PayPal callout and the receipt link were each held too briefly and are now held longer.
- **SFX:** every effect was re-timed so its peak lands one frame after its picture.

## Measured (pass 2)
- `lint`: 0 errors, 0 warnings.
- `check --json`: ok, 0 errors, 10 warnings kept on purpose:
  - `text_below_floor` at 9.1 s: the whole real page at 0.75x is the establishing shot. The same bill text is readable at 1.3x from 3.4 s to 8.5 s.
  - `line_unread` on the hero badges (35.6 s, 40.6 s): each continues as the same badge in its row.
  - `line_unread` on `#pa-label`, `#in-hero` and `#in-billed`: each continues across a scene seam, same text in the same place.
  - `line_unread` on the invoice items at 79.6 s: they are on screen from 70.3 s; the checker counts from the blur-out.
- `snapshot --review`: all 4 seams (21.6, 57.4, 67.15, 80.35 s) are invisible holds or a match cut on the number. The beats read in order.
- **Not measured:** the mix. No render was made, so `hyperframes audio <video>` has not run. Nothing was heard, including the music crossfade at 82.3–83.3 s and the levels of the 0.42 lifts.

## Still open
- P2 · 39.6 s · CT: the struck $1,650.00 overlaps the rolling $298.00 for about 0.3 s during the shrink.
- P2 · phone width · 28 px labels are hard to read at 360 px; the numbers read fine.
- P2 · the HeyGen track's licence: the catalog API returns no per-track licence text. Check HeyGen's terms before any monetised use.
- Weakest shot: the checkout (60–67 s) is a static screenshot with a pan. A captured clip of the real PayPal flow would beat it.

## Creative calls (from pass 1, still true)
- Built storyline A. Not built: B "The envelope" and C "The math out loud".
- One camera world over the real `ui_page.png`, with the bill box rebuilt crisp in place.
- Cards morph through clip-path. Amounts roll on digit wheels (adapted from the registry's `number-wheel`). The $4,445.00 → $1,882.38 carrier survives every seam.
- Receipt and invoice are rebuilt from `receipt.json` and `paypal_readback.json`, because `ui_receipt.png` was captured under a modal overlay.

## Defaults checked (BANNED)
No dark void, glow, gradients, glass, serif/cream look, three-card row, docked logo or corner labels. The audit and sum are left-anchored; only the receipt, invoice, claim and end card are centred.
