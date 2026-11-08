"""Narration with the owner's ElevenLabs account. Key from the environment (ELEVENLABS_API_KEY, loaded from Keychain).

Usage:
  voice.py sample <voice-name-prefix> <out.mp3> "<text>"
  voice.py lines <voice-name-prefix> <lines.json> <out_dir>     lines.json: [{"id": "N1", "text": "..."}]
Writes MP3 files and, for `lines`, <out_dir>/timings.json with each line's duration (from the file).
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import requests

API = "https://api.elevenlabs.io"
MODEL = "eleven_multilingual_v2"
SETTINGS = {"stability": 0.5, "similarity_boost": 0.75, "style": 0.2, "use_speaker_boost": True}


def key() -> str:
    k = os.environ.get("ELEVENLABS_API_KEY", "")
    if not k:
        sys.exit("ELEVENLABS_API_KEY is not set")
    return k


def voice_id(prefix: str) -> str:
    r = requests.get(f"{API}/v2/voices", params={"page_size": 100}, headers={"xi-api-key": key()}, timeout=30)
    r.raise_for_status()
    for v in r.json()["voices"]:
        if v["name"].lower().startswith(prefix.lower()):
            return v["voice_id"]
    sys.exit(f"no voice starting with {prefix!r}")


def speak(vid: str, text: str, out: Path, previous: str = "", following: str = "") -> None:
    body = {"text": text, "model_id": MODEL, "voice_settings": SETTINGS}
    if previous:
        body["previous_text"] = previous  # keeps intonation continuous across separately generated lines
    if following:
        body["next_text"] = following
    r = requests.post(f"{API}/v1/text-to-speech/{vid}", params={"output_format": "mp3_44100_128"},
                      headers={"xi-api-key": key(), "Content-Type": "application/json"}, json=body, timeout=120)
    if r.status_code != 200:
        sys.exit(f"ElevenLabs {r.status_code}: {r.text[:200]}")
    out.write_bytes(r.content)


def duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return round(float(out.strip()), 3)


def main() -> None:
    mode, prefix = sys.argv[1], sys.argv[2]
    vid = voice_id(prefix)
    if mode == "sample":
        out = Path(sys.argv[3])
        speak(vid, sys.argv[4], out)
        print(f"{out} {duration(out)}s")
        return
    lines = json.loads(Path(sys.argv[3]).read_text())
    out_dir = Path(sys.argv[4])
    out_dir.mkdir(parents=True, exist_ok=True)
    timings = {}
    for i, line in enumerate(lines):
        out = out_dir / f"{line['id']}.mp3"
        prev = lines[i - 1]["text"] if i else ""
        nxt = lines[i + 1]["text"] if i + 1 < len(lines) else ""
        speak(vid, line["text"], out, prev, nxt)
        timings[line["id"]] = duration(out)
        print(f"{line['id']:<5} {timings[line['id']]:6.2f}s", flush=True)
    (out_dir / "timings.json").write_text(json.dumps(timings, indent=1))


if __name__ == "__main__" and sys.argv[1] != "one_take":
    main()


def one_take(prefix: str, lines_path: Path, starts: dict, out_mp3: Path, out_json: Path) -> None:
    """The whole script as ONE continuous take (no per-line resets), with <break> pauses sized to the film's beat
    starts, and per-line start/end times from ElevenLabs' character alignment."""
    import base64
    lines = json.loads(Path(lines_path).read_text())
    parts, prev_end_est = [], None
    for i, line in enumerate(lines):
        if i:
            gap = starts[line["id"]] - (starts[lines[i - 1]["id"]] + line_est[lines[i - 1]["id"]])
            parts.append(f'<break time="{min(3.0, max(0.4, gap)):.1f}s" />')
        parts.append(line["text"])
    text = " ".join(parts)
    vid = voice_id(prefix)
    r = requests.post(f"{API}/v1/text-to-speech/{vid}/with-timestamps", params={"output_format": "mp3_44100_128"},
                      headers={"xi-api-key": key(), "Content-Type": "application/json"},
                      json={"text": text, "model_id": MODEL, "voice_settings": SETTINGS}, timeout=300)
    if r.status_code != 200:
        sys.exit(f"ElevenLabs {r.status_code}: {r.text[:300]}")
    data = r.json()
    out_mp3.write_bytes(base64.b64decode(data["audio_base64"]))
    al = data["alignment"]
    chars, st, en = al["characters"], al["character_start_times_seconds"], al["character_end_times_seconds"]
    joined = "".join(chars)
    timings, cursor = {}, 0
    for line in lines:
        i = joined.find(line["text"], cursor)
        if i < 0:
            sys.exit(f"could not align {line['id']}")
        j = i + len(line["text"]) - 1
        timings[line["id"]] = {"start": round(st[i], 3), "end": round(en[j], 3)}
        cursor = j + 1
    out_json.write_text(json.dumps({"file": out_mp3.name, "duration": duration(out_mp3), "lines": timings}, indent=1))
    print(json.dumps(timings, indent=1))


line_est: dict = {}

if __name__ == "__main__" and sys.argv[1] == "one_take":
    # one_take <voice> <lines.json> <starts.json {id: start_s}> <per-line durations json> <out.mp3> <out.json>
    starts_in = json.loads(Path(sys.argv[4]).read_text())
    line_est.update(json.loads(Path(sys.argv[5]).read_text()))
    one_take(sys.argv[2], Path(sys.argv[3]), starts_in, Path(sys.argv[6]), Path(sys.argv[7]))
