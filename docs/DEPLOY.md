# Judge demo on Hugging Face Spaces

Free CPU Space, Docker SDK, no card. The app runs from `Dockerfile` (user 1000, port 7860).

## Steps
1. **Owner:** sign in at huggingface.co → New Space → name `billcheck`, SDK **Docker** (blank template), hardware **CPU basic (free)**, visibility **Public**.
2. **Owner:** Space → Settings → **Variables and secrets** → add three **secrets** (never variables):
   `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET` (the BillCheck sandbox app on the US sandbox merchant), `FIREWORKS_API_KEY`.
3. **Owner:** create a Hugging Face **write** token for this Space only (Settings → Access Tokens → fine-grained, write access to `billcheck`) and store it in the macOS Keychain as `HF_TOKEN` (pop-up box, never in chat or a file).
4. **Conductor:** after the pre-publish scan passes, push a clean snapshot of `main` (no git history) to the Space's git remote, using `HF_TOKEN` from the Keychain.
5. **Conductor:** check the live app: the page loads inside huggingface.co and at `*.hf.space`; a sample audit returns $1,882.38 for C08; the PayPal buttons load; the rate limit counts per visitor (a burst from one connection gets 429 while a second connection still works).

## Limits
- The free Space sleeps after about 48 hours without visits; the first visit then takes a minute or two.
- The model spend ledger lives on the Space's temporary disk, so a restart resets the $2/day cap; the per-visitor rate limit still applies.
- Sandbox money only. PayPal sandbox test cards: https://developer.paypal.com/tools/sandbox/card-testing/
