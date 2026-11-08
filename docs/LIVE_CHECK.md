# Live sandbox check (8 Nov 2026)

End to end on a locally running BillCheck, driven in Chrome: sample bill C08 (synthetic, $4,445.00 billed) → AI reader → audit → PayPal JS SDK card checkout with PayPal's published sandbox test Visa → server capture → corrected invoice.

| Step | Result read back from PayPal's sandbox API |
|---|---|
| Order capture | `5BD33334PD5796707`: COMPLETED, $1,882.38 USD, final capture |
| Corrected invoice | `INV2-DTFL-LKDR-R2Z5-5VM8`: MARKED_AS_PAID, total $1,882.38, paid $1,882.38 |
| Invoice lines | ED visit (99284) $1,189.38; CT head (70450) $298.00; CMP (80053) $180.00; CBC (85025) $95.00; injection (96372) $120.00 |
| Recorded payment note | "Paid through PayPal Orders, capture 5BD33334PD5796707" |

What it took (kept so the setup can be reproduced):
- The first sandbox merchant was registered in Egypt; PayPal refused the capture with `COMPLIANCE_VIOLATION`. A US sandbox business account and a new app (`BillCheck`, Merchant) fixed it.
- The new app was created without the Invoicing feature (403 `NOT_AUTHORIZED`). After ticking Invoicing, PayPal took about 15 minutes to add the invoicing scope to the app's token; the receipt's retry then issued the invoice for the same capture, with no second charge.
- Found and fixed during this check: the receipt said the invoice was issued even when it was pending.
