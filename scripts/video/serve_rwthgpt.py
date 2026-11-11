"""Run BillCheck locally for a screen recording, with the same model (GPT-OSS 120B) served by RWTHgpt.

Why: Fireworks, which the app normally uses, was unavailable for this recording. RWTHgpt (KI:connect, a
university-hosted service) serves the same open-weight model, gpt-oss-120b.
Only the synthetic sample bills are sent. Everything else (rules, audit, PayPal sandbox) is the unchanged app.

Keys come from the macOS Keychain: RWTHGPT_API_KEY, PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET (sandbox).
Usage: .venv/bin/python scripts/video/serve_rwthgpt.py [port]
"""

import getpass
import subprocess
import sys
from typing import Optional

import requests
import uvicorn

from billcheck.llm import MAX_OUTPUT_TOKENS, LLMError, LLMReply
from billcheck.web.app import create_app

API_URL = "https://chat.kiconnect.nrw/api/v1/chat/completions"
MODEL = "gpt-oss-120b"


def keychain(service: str, account: Optional[str] = None) -> str:
    cmd = ["security", "find-generic-password", "-s", service, "-w"]
    if account:
        cmd[2:2] = ["-a", account]
    out = subprocess.run(cmd, capture_output=True, text=True).stdout.strip()
    if not out:
        sys.exit(f"missing Keychain item {service}")
    return out


class RwthGptLLM:
    """Same chat() contract as billcheck.llm.FireworksLLM; no cost (free university quota)."""

    def __init__(self, api_key: str, timeout_s: float = 60.0):
        self.api_key, self.timeout_s = api_key, timeout_s

    def chat(self, messages: list, json_mode: bool = False, schema: Optional[dict] = None) -> LLMReply:
        body = {"model": MODEL, "messages": messages, "temperature": 0, "max_tokens": MAX_OUTPUT_TOKENS}
        if json_mode:  # same constraint as FireworksLLM; RWTHgpt enforces a schema only in the json_schema form
            body["response_format"] = ({"type": "json_schema", "json_schema": {"name": "bill", "schema": schema}}
                                       if schema else {"type": "json_object"})
        try:
            resp = requests.post(API_URL, json=body, timeout=self.timeout_s,
                                 headers={"Authorization": f"Bearer {self.api_key}"})
            resp.raise_for_status()
            text = resp.json()["choices"][0]["message"]["content"] or ""
        except (requests.RequestException, ValueError, KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"model call failed: {type(exc).__name__}") from exc
        return LLMReply(text=str(text), cost_usd=0.0)


def main() -> None:
    import os
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    os.environ["PAYPAL_CLIENT_ID"] = keychain("PAYPAL_CLIENT_ID")
    os.environ["PAYPAL_CLIENT_SECRET"] = keychain("PAYPAL_CLIENT_SECRET")
    rwth_key = keychain("RWTHGPT_API_KEY", getpass.getuser())
    app = create_app(llm_factory=lambda: RwthGptLLM(rwth_key))
    uvicorn.run(app, host="127.0.0.1", port=port, proxy_headers=False, log_level="warning")


if __name__ == "__main__":
    main()
