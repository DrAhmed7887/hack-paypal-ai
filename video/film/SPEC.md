# SPEC: BillCheck demo film, storyline A "One bill, one number"

GOAL: a judge follows one real bill ($4,445.00) through BillCheck and leaves knowing that every dollar of the $1,882.38 they can pay is earned on screen, paid through PayPal sandbox and printed back as an itemized invoice (suggested amounts) marked paid.

OUTPUT: HyperFrames, 1920 x 1080, 30 fps.

TIME: 94.0 s x 30 = 2820 frames. Narration (ElevenLabs "Sarah", L1-L10, 73.0 s) is the clock; no music yet, so no BPM grid.

## Voice placement (one continuous take `narration_take.mp3` at 0.3 s; line starts from narration_take.json + 0.3; anchor words from `transcribe --model base.en`)

| Line | Start | Anchor words (absolute) |
| --- | --- | --- |
| L1 | 0.30 | "four thousand four hundred forty-five" 0.5-3.4 · "five lines" 3.52 · "nothing tells you" 5.22 |
| L2 | 8.45 | "BillCheck" 8.94 · "paste" 10.55 · "AI reads" 11.90 · "code checks" 13.56 |
| L3 | 16.95 | "each line it can price" 17.15 · "Medicare rate" 20.44 |
| L4 | 21.93 | "emergency visit" 22.09 · "2,400" 23.46 · "Medicare pays" 25.13 · "private plans" 27.15 · "2.79" 29.17 · "so the negotiation reference" 31.53 · "1189" 34.48 |
| L5 | 35.99 | "CT scan" 36.15 · "1650" 37.08 · "298" 39.29 |
| L6 | 41.90 | "blood tests" 42.09 · "included" 43.17 · "injection" 45.22 · "no confirmed benchmark" 46.09 · "BillCheck says so" 48.09 |
| L7 | 51.26 | "what's left" 51.26 · "adds up" 52.22 · "$1,882.38" 53.35 (ends 56.31) |
| L8 | 58.44 | "goes straight into" 58.56 · "PayPal's sandbox checkout" 59.77 · "server sets it" 61.96 (ends 64.27) |
| L9 | 67.34 | "payment captured" 67.34 · "BillCheck then issues" 68.80 · "itemized invoice" 70.27 · "suggested amounts" 71.67 · "provider's sandbox account" 73.24 · "marks it paid" 75.13 · "same payment" 77.25 |
| L10 | 79.52 | "one bill" 79.52 · "one number you can pay" 79.80 · "every rule signed by a physician" 82.34 (voice ends 84.91) |

Scenes: bill 0-21.6 · audit 21.6-57.4 · pay 57.4-67.15 · invoice 67.15-80.35 · close 80.35-94.0.

## LOOK (the app's own medium: product UI on its own ground)

- Ground `#f6f7f5` flat, no texture, no gradient, 0% grain, 0% vignette. PayPal world: `#ffffff` (its own page).
- Cards `#ffffff`, 2 px edge `#e2e6e3` at video scale (1 px in the app), radius 14 px (rows) and 20 px (hero cards). No drop shadows.
- Ink `#1c2321`; muted `#5d6763`; accent teal `#0f6e5c` (soft `#e3f1ed`), allowed on: the BillCheck wordmark, "x 2.79", the check chips, the landed $1,882.38 and the MARKED_AS_PAID stamp. Flag red `#a3361f` on `#fbe9e5` only on the two flagged amounts and their "Above negotiation reference" badges. Packaged badge `#34406b` on `#eef0f6`; not-available badge `#5d6763` on `#f0f1f0` (all from `src/billcheck/web/static/style.css`).
- Type: Inter (the app's face) 400 / 700 / 900, money in `font-variant-numeric: tabular-nums`. Hero money 168-220 px / 900, equation terms 120 px / 900 in two rows, row titles 44 px / 700, row amounts 52 px / 700, labels 28-34 px / 400. Bill text JetBrains Mono 27.2 px in image space (the app's ui-monospace; nearest bundled mono).
- Floor: every line meant to be read >= 28 px at 1080. Real screenshots shown at 1.0 image px per screen px (= 2x CSS) when isolated (ui_pay, ui_totals), the page plate at 0.75-3.4x as a camera world.
- Medium rule: the product is a stack of white cards on a pale ground; cards morph (clip-path inset on edge + fill layers), never fade-swap; numbers roll on per-digit wheels (registry `number-wheel`, adapted to roll down).

## OBJECTS

- The bill: the app's own "Bill text" box rebuilt crisp in place over `ui_page.png` (rect x 594-2009, y 1262-1648 image px; text from `render_table(C08)` verbatim), so the camera can push to 3.4x.
- The BillCheck page: `ui_page.png` as a 2560 x 1800 world the camera travels across.
- Five line rows/cards: rebuilt from `audit.json` (description, "Code nnnnn", billed, benchmark, badge label, explanation) in the app's `.line` style at video scale.
- PayPal pay card: `ui_pay.png` (real). PayPal checkout: `pp_checkout.png` cropped to y < 1150 (cookie banner out; card-brand logos stay blurred as captured).
- Receipt: rebuilt from `receipt.json` in the app's `.receipt` style (the captured `ui_receipt.png` is dimmed by a modal overlay, so it is not usable).
- Invoice: rebuilt from `paypal_readback.json` (id, item names and amounts, status MARKED_AS_PAID, note "Originally billed: $4,445.00.").
- Cursor: none (no real click is shown; the button is pressed by the arriving number, which is the cause).

## MOTION

- Enter: `expo.out` 0.45-0.7 s. Camera and container morphs: `power2.inOut` 0.6-0.9 s (power3.inOut for carries). Zoom-through / exits: `power3.in` 0.3-0.35 s, exits 40-50% of entrances.
- Number rolls: 1.0-1.2 s `power3.out`, columns staggered 0.05 s right-to-left, landing on the spoken number.
- Badges: `back.out(1.6)` scale 0.6 -> 1 in 0.3 s (position/scale only), with a pop.
- Stagger: rows 0.06 s, words 0.067 s, letters 0.05 s, invoice lines 0.3 s.
- Motion blur on fast moves via `filter: blur()` peaking 6-12 px mid-move on the carried number and the zoom-through.
- Landed text is dead still.

## SHOTS (absolute time · frames)

| # | Time | Frames | Hero move | Reads | Sound | Hand-off |
| --- | --- | --- | --- | --- | --- | --- |
| 1 Hook | 0.0-3.4 | 0-102 | camera at 3.0x on the bill's charge column and TOTAL $4,445.00; teal marker sweeps under the total (0.35-0.9) | "$4,445.00" | VO | pull back on "five lines" |
| 2 Tension | 3.4-8.5 | 102-255 | pull back to 1.3x (0.8 s); five line bands at 3.6; "Price to compare ?" column at 5.2-5.6 | the empty column | pop 5.3 | column retracts 7.9 |
| 3 Reveal | 8.5-11.85 | 255-356 | pull back to the whole real page at 0.75x on "This is BillCheck"; down to the chip and box on "paste" (10.45) | BillCheck page | whoosh 8.82 | lines lift |
| 4 AI reads | 11.85-16.9 | 356-507 | the five lines lift out and grow into row cards while the page recedes (0.75 -> 0.68x, blur 15 px) behind a ground scrim; GPT-OSS label 12.15; "matches the bill" checks 13.6 | rows, checks | whoosh-short, pop | same rows |
| 5 Price | 16.9-21.6 | 507-648 | three unpriced rows dim at 17.4; Medicare $426.30 / $106.81 land at 20.4 | Medicare values | click-soft 20.36 | ED row morphs |
| 6 ED proof | 21.6-36.6 | 648-1098 | ED row opens to a 660 px hero (22.0); $2,400.00 red at 23.45; $426.30 carries into a 120 px equation at 25.1; RAND label 27.2, "x 2.79" 29.15; "=" 31.6; "$1,189.38" 34.45; amount rolls 34.5-35.5; badge 35.55; caveat header from 35.75 | equation, badge | ticks, pop | folds back |
| 7 CT proof | 36.6-41.85 | 1098-1256 | CT row opens to a 640 px hero; $106.81 x 2.79 = $298.00 (39.25); $1,650.00 struck, $298.00 rolls in 39.65; badge 40.55 | equation | whoosh, tick, pop | folds back |
| 8 Not flagged | 41.85-51.3 | 1256-1539 | labs and injection slide back in from the right; packaged badges 43.2; not-available badge 46.55; injection explanation types 48.1-49.4 | badges, explanation | pops, typing | amounts stay |
| 9 Sum | 51.3-57.4 | 1539-1722 | rows dissolve; amounts stack right at 1.2x; carrier $4,445.00 (220 px) rolls to $1,882.38 landing 53.4; ui_totals at 1.1x from 54.6; music up 56.4 | "Suggested amount $1,882.38" | ticks | all but the number exit |
| 10 Into PayPal | 57.4-59.95 | 1722-1799 | pay card rises; $1,882.38 arcs into the yellow button 58.55-59.05, button presses; zoom through 59.6-59.95 on music section E | pay card | whoosh, click-soft, whoosh-short | yellow fills frame |
| 11 Checkout | 59.95-67.15 | 1799-2015 | real PayPal checkout whips up; callout at 61.9 / 62.35, held to 64.4; pan to the filled test card 64.5-65.25 with label (64.75-66.25); punch-in on the amount 66.75-67.15 | callout, test card label | whoosh-short 67.02 | match cut on the number |
| 12 Captured | 67.15-69.4 | 2015-2082 | $1,882.38 lands big then carries into "Paid" as the receipt builds; music section F at 67.9 | Payment complete (sandbox) | register (peak 67.94) | invoice link morphs |
| 13 Invoice | 69.4-79.5 | 2082-2385 | invoice link grows into a 1600 x 860 invoice (69.4); five lines print 70.3-71.5; total 71.75; provider line 73.25; MARKED_AS_PAID stamp 75.15; capture line 77.25 | items, stamp | ticks, click | total carries |
| 14 Claim | 79.5-84.95 | 2385-2549 | invoice total grows to centre (168 px teal); "$4,445.00 billed" struck above; sources per word at 82.35 | "$1,882.38" | - | blur out |
| 15 End card | 84.95-94.0 | 2549-2820 | wordmark outline wipe then teal fill (lands 86.2); repo typed 86.85; synthetic/sandbox line 88.15; music up to 0.32 then 1.5 s fade | repo | impact 86.16, typing 86.85 | end |

## SOUND

- VO: one continuous take at volume 1 (file unchanged).
- Music: HeyGen catalog track (`assets/music/bed.wav`, 82 s, ~120 BPM grid, beats on x.015 / x.515 s), placed at 1.3 s so its section E (track 58.5 s) lands on the PayPal zoom-through (59.8 s) and section F (66.6 s) on the capture (67.9 s). Volume lane: 0.14 under the voice, 0.42 in the payoff pauses 56.4-58.4 s and 64.35-67.3 s. A tail clip re-enters section F 6 bars earlier (media 69 s) at 82.3 s with a 1 s crossfade, rises to 0.32 after the voice ends, fades out 1.5 s at 94 s.
- SFX: bundled HyperFrames library (Pixabay licence) + one CC0 cash register (Openverse). See `CREDITS.md`. 0.2-0.5 volume, each on a visible cause.

## BANNED

- Defaults: dark void ground; glow, bloom, particles; purple/blue or mesh gradients; glass cards; cream-paper serif look; numbered 01/02 labels; small mono caps labels; everything centred; everything fading and sliding up; text moving while read; titles drifting after landing; corner labels, frame borders, HUD; three cards in a row; KPI grids; title over a dimmed screenshot; logo docked in a corner.
- This film: any drawn UI that the app does not have; invented numbers; the words fair, standard, reasonable, error, overcharge, fraud, wrong, corrected (for a price or charge); accuracy statistics; third-party logos other than PayPal's own checkout and buttons; unblurred card-brand logos; the PayPal cookie banner; a typing-into-a-prompt opener; a slow creeping zoom on a held title; the same entrance twice in a row.

## QA frames

- 0.0: bill total big, never blank (thumbnail).
- 6.5: five lines + "Price to compare ?" column readable.
- 9.9: whole real BillCheck page, brand visible.
- 14.5: five rows with "matches the bill" chips.
- 20.8: ED/CT Medicare values, three rows dimmed.
- 35.5: ED hero: equation $426.30 x 2.79 = $1,189.38, amount $1,189.38 with $2,400.00 struck, red badge.
- 40.0: CT hero $106.81 x 2.79 = $298.00.
- 49.5: three not-flagged rows with badges and typed explanation.
- 56.5: $1,882.38 teal + ui_totals.
- 59.9: number inside the PayPal button.
- 63.9: checkout with callout; no cookie banner.
- 73.0: invoice lines printed.
- 77.5: MARKED_AS_PAID stamp.
- 84.0: claim.
- 91.0: wordmark + repo + synthetic/sandbox line.
