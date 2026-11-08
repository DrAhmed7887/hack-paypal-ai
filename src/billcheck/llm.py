"""Fireworks chat client with a hard daily spend cap (Ahmed's OK: $2/day on the Fireworks credit)."""

import fcntl
import json
import math
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Callable, Optional

import requests

API_URL = "https://api.fireworks.ai/inference/v1/chat/completions"
DEFAULT_MODEL = "accounts/fireworks/models/gpt-oss-120b"
# USD per 1M tokens, from fireworks.ai/pricing (read 8 Nov 2026). Unknown models are refused.
PRICES = {DEFAULT_MODEL: (0.15, 0.60)}
MAX_OUTPUT_TOKENS = 2000


def _cap_from_env() -> float:
    raw = os.environ.get("BILLCHECK_DAILY_CAP_USD", "2.00")
    try:
        cap = float(raw)
    except ValueError as exc:
        raise ValueError("BILLCHECK_DAILY_CAP_USD must be a number") from exc
    if not math.isfinite(cap) or not 0 < cap <= 20:
        raise ValueError("BILLCHECK_DAILY_CAP_USD must be between 0 and 20")
    return cap


class SpendCapReached(RuntimeError):
    pass


class LLMError(RuntimeError):
    pass


@dataclass(frozen=True)
class LLMReply:
    text: str
    cost_usd: float


class SpendGuard:
    """Per-day spend ledger. Each call reserves its worst-case cost under a file lock before it runs and
    settles to the real cost afterwards; any ledger problem fails closed (no call)."""

    def __init__(self, cap_usd: Optional[float] = None, ledger_dir: Optional[Path] = None,
                 today: Callable[[], date] = date.today):
        self.cap_usd = _cap_from_env() if cap_usd is None else cap_usd
        self.ledger_dir = ledger_dir or Path.home() / ".billcheck" / "spend"
        self.today = today

    def _path(self) -> Path:
        return self.ledger_dir / f"{self.today().isoformat()}.json"

    def _read(self) -> float:
        path = self._path()
        if not path.exists():
            return 0.0
        try:
            usd = float(json.loads(path.read_text())["usd"])
        except (ValueError, KeyError, TypeError, OSError) as exc:
            raise SpendCapReached("spend ledger unreadable; refusing model calls") from exc
        if not math.isfinite(usd) or usd < 0:
            raise SpendCapReached("spend ledger invalid; refusing model calls")
        return usd

    def _write(self, usd: float) -> None:
        tmp = self._path().with_suffix(".tmp")
        tmp.write_text(json.dumps({"usd": round(usd, 6)}))
        os.replace(tmp, self._path())

    def _locked(self, update: Callable[[float], float]) -> float:
        try:
            self.ledger_dir.mkdir(parents=True, exist_ok=True)
            with open(self.ledger_dir / ".lock", "w") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                new = update(self._read())
                self._write(new)
                return new
        except OSError as exc:
            raise SpendCapReached("spend ledger not writable; refusing model calls") from exc

    def spent_today(self) -> float:
        return self._read()

    def check(self) -> None:
        if self._read() >= self.cap_usd:
            raise SpendCapReached(f"daily model budget of ${self.cap_usd:.2f} reached")

    def reserve(self, usd: float) -> None:
        def update(spent: float) -> float:
            if spent + usd > self.cap_usd:
                raise SpendCapReached(f"daily model budget of ${self.cap_usd:.2f} reached")
            return spent + usd
        self._locked(update)

    def record(self, usd: float) -> None:
        self._locked(lambda spent: spent + usd)


class FireworksLLM:
    def __init__(self, api_key: Optional[str] = None, model: str = DEFAULT_MODEL,
                 guard: Optional[SpendGuard] = None, timeout_s: float = 60.0):
        self.api_key = api_key or os.environ.get("FIREWORKS_API_KEY", "")
        if not self.api_key:
            raise LLMError("FIREWORKS_API_KEY is not set")
        if model not in PRICES:
            raise LLMError(f"no known price for model {model}; refusing to call it")
        self.model, self.guard, self.timeout_s = model, guard or SpendGuard(), timeout_s

    def worst_case_usd(self, messages: list) -> float:
        chars = sum(len(str(m.get("content", ""))) for m in messages)
        price_in, price_out = PRICES[self.model]
        return (chars / 2 * price_in + MAX_OUTPUT_TOKENS * price_out) / 1e6  # >= real tokens

    def chat(self, messages: list, json_mode: bool = False, schema: Optional[dict] = None) -> LLMReply:
        reserved = self.worst_case_usd(messages)
        self.guard.reserve(reserved)  # fails closed; the reservation stays if anything below fails
        body = {"model": self.model, "messages": messages, "temperature": 0, "max_tokens": MAX_OUTPUT_TOKENS}
        if json_mode:
            body["response_format"] = {"type": "json_object", **({"schema": schema} if schema else {})}
        try:
            resp = requests.post(API_URL, json=body, timeout=self.timeout_s,
                                 headers={"Authorization": f"Bearer {self.api_key}"})
            resp.raise_for_status()
            data = resp.json()
            usage = data["usage"]
            cost = (int(usage["prompt_tokens"]) * PRICES[self.model][0]
                    + int(usage["completion_tokens"]) * PRICES[self.model][1]) / 1e6
            text = data["choices"][0]["message"]["content"] or ""
        except (requests.RequestException, ValueError, KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"model call failed: {type(exc).__name__}") from exc
        self.guard.record(cost - reserved)  # settle the reservation to the real cost
        return LLMReply(text=str(text), cost_usd=cost)
