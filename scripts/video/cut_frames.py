"""Cut the frame-by-frame recording (record_frames.py) into the judge demo: real screens, one idea per scene,
titles of 5 words or fewer, the title on screen from the first frame, voice + music bed at about -16 LUFS.

Scene plan from the video-director review (11 Nov 2026). Each scene starts where the scroll to its content starts,
so a scene held to fit its voice line freezes on its own content. Footage is never rebuilt: scenes are ranges of real frames.
Waits are shortened only where a scene says so on screen; a scene shorter than its voice line holds its last frame.
Audio: the BillCheck narration takes L1-L9 (ElevenLabs, owner's account; L10 dropped), the Clocked film's music bed
and tick/pop effects (ElevenLabs, owner's account).
Usage: .venv/bin/python scripts/video/cut_frames.py
Output: video/walkthrough/billcheck_demo.mp4
"""

import json
import subprocess
import tempfile
from html import escape
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WALK = REPO / "video" / "walkthrough"
FRAMES = WALK / "frames"
VOICE = REPO / "video" / "film" / "assets" / "voice"
CLOCKED_AUDIO = Path.home() / "Projects" / "hack-clocked" / "video" / "film" / "assets" / "audio"
MUSIC, TICK, POP = CLOCKED_AUDIO / "bed.wav", CLOCKED_AUDIO / "raw" / "sfx_tick_a.mp3", CLOCKED_AUDIO / "raw" / "sfx_pop.mp3"
OUT = WALK / "billcheck_demo.mp4"
FPS, BG = 30, "#F3F6F5"
VENC = ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS), "-preset", "medium", "-crf", "18", "-an"]


def run(args: list) -> None:
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)


def seconds(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return float(out)


def png(html: str, path: Path, transparent: bool = True) -> Path:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1920, "height": 1080})
        page.set_content("<html><body style=\"margin:0;width:1920px;height:1080px;font-family:Inter,Helvetica,Arial,"
                         f"sans-serif;background:{'transparent' if transparent else BG}\">{html}</body></html>")
        page.screenshot(path=str(path), omit_background=transparent)
        browser.close()
    return path


def caption_html(label: str, title: str, sub: str, left: int = 48, bottom: int = 48, width: int = 1060) -> str:
    sub_html = f"<div style='font-size:30px;line-height:1.3;color:#CFE3DF;margin-top:10px'>{escape(sub)}</div>" if sub else ""
    return (f"<div style='position:absolute;left:{left}px;bottom:{bottom}px;max-width:{width}px;padding:24px 34px 26px;"
            "background:rgba(14,38,35,.93);border-radius:16px;border-left:6px solid #3FB9A6'>"
            "<div style='font-family:Menlo,monospace;font-weight:700;font-size:26px;letter-spacing:.12em;"
            f"text-transform:uppercase;color:#7FD1C4'>{escape(label)}</div>"
            f"<div style='font-weight:800;font-size:56px;line-height:1.08;color:#fff;margin-top:6px'>{escape(title)}</div>"
            f"{sub_html}</div>")


def main_scene(tmp: Path, sc: dict) -> Path:
    """Real main-page frames [a, b), optionally sped up, held on the last frame to fill the scene, captioned."""
    a, b, length = sc["a"], sc["b"], sc["length"]
    footage = (b - a) / FPS
    speed = max(1.0, footage / length) if sc.get("fit") else 1.0
    hold = max(0.0, length - footage / speed)
    cap = png(caption_html(sc["label"], sc["title"], sc.get("sub", "")), tmp / f"{sc['id']}_cap.png")
    out = tmp / f"{sc['id']}.mp4"
    vf = (f"[0:v]trim=end_frame={b - a},setpts=(PTS-STARTPTS)/{speed:.4f},fps={FPS},tpad=stop_mode=clone:stop_duration={hold:.3f}[v];"
          "[v][1:v]overlay=0:0,format=yuv420p[o]")
    run(["-framerate", str(FPS), "-start_number", str(a), "-i", str(FRAMES / "main" / "%05d.jpg"), "-i", str(cap),
         "-frames:v", str(round(length * FPS)), "-filter_complex", vf, "-map", "[o]", *VENC, str(out)])
    return out


def popup_scene(tmp: Path, sc: dict) -> Path:
    """The PayPal window's real frames on the app's light ground, caption on the left."""
    a, b, length = sc["a"], sc["b"], sc["length"]
    hold = max(0.0, length - (b - a) / FPS)
    cap = png(caption_html(sc["label"], sc["title"], sc.get("sub", ""), left=80, bottom=420, width=860),
              tmp / f"{sc['id']}_cap.png")
    out = tmp / f"{sc['id']}.mp4"
    vf = (f"[0:v]trim=end_frame={b - a},setpts=PTS-STARTPTS,scale=-2:1020:flags=lanczos,pad=1920:1080:1920-iw-110:30:color={BG.replace('#', '0x')},"
          f"tpad=stop_mode=clone:stop_duration={hold:.3f}[v];[v][1:v]overlay=0:0,format=yuv420p[o]")
    run(["-framerate", str(FPS), "-start_number", str(a), "-i", str(FRAMES / "popup" / "%05d.jpg"), "-i", str(cap),
         "-frames:v", str(round(length * FPS)), "-filter_complex", vf, "-map", "[o]", *VENC, str(out)])
    return out


def end_card(tmp: Path, receipt: dict, length: float) -> Path:
    rows = [("Paid (sandbox)", receipt["amount"]), ("PayPal capture", receipt["capture"]),
            ("Itemized invoice", receipt["invoice"] + " · marked paid")]
    table = "".join(f"<div style='display:flex;gap:28px;font-size:36px;margin:10px 0'><span style='width:330px;"
                    f"color:#4B6B66'>{escape(k)}</span><b>{escape(v)}</b></div>" for k, v in rows)
    html = ("<div style='padding:190px 190px;color:#12302C'>"
            "<div style='font-weight:800;font-size:72px;margin-bottom:34px'>BillCheck: read back from this run</div>"
            f"{table}<div style='margin-top:46px;font-size:30px;color:#4B6B66'>Synthetic bill · PayPal sandbox money · "
            "AI reader: GPT-OSS 120B (served by RWTHgpt for this recording)</div>"
            "<div style='margin-top:18px;font-family:Menlo,monospace;font-weight:700;font-size:34px;color:#0B5F57'>"
            "github.com/DrAhmed7887/hack-paypal-ai</div></div>")
    still = png(html, tmp / "end.png", transparent=False)
    out = tmp / "end.mp4"
    run(["-loop", "1", "-framerate", str(FPS), "-t", f"{length}", "-i", str(still), *VENC, str(out)])
    return out


def scenes(m: dict, receipt: dict) -> list:
    v = {i: seconds(VOICE / f"L{i}.mp3") for i in range(1, 10)}
    pad = 0.7
    return [
        {"id": "s1", "a": 0, "b": m["check"], "voice": 1, "clicks": [m["pick"]], "label": "Synthetic bill · C08",
         "title": "A $4,445 hospital bill"},
        {"id": "s2", "a": m["check"], "b": m["ai_end"], "voice": 2, "fit": True, "clicks": [m["check"]],
         "label": "AI reader · GPT-OSS 120B", "title": "BillCheck reads every line",
         "sub": f"Real wait {m['ai_wait_s']:.0f} s, shortened here"},
        {"id": "s3", "a": m["ai_end"], "b": m["line1_from"], "voice": 3, "label": "Audit result",
         "title": "$2,562.62 in question", "sub": "AI summary: every dollar figure checked against the audit"},
        {"id": "s4", "a": m["line1_from"], "b": m["line2_from"], "voice": 4, "label": "ED visit · 99284",
         "title": "5.63× Medicare", "sub": "$2,400.00 billed → $1,189.38 negotiation reference"},
        {"id": "s5", "a": m["line2_from"], "b": m["line3_from"], "voice": 5, "label": "CT head · 70450",
         "title": "15.45× Medicare", "sub": "$1,650.00 billed → $298.00"},
        {"id": "s6", "a": m["line3_from"], "b": m["pay_from"], "voice": 6, "label": "Labs · injection",
         "title": "Some lines stay unflagged", "sub": "Included in the visit payment, or no confirmed benchmark"},
        {"id": "s7", "a": m["pay_from"], "b": m["popup_open"], "voice": 7, "clicks": [m["card_click"]],
         "label": "PayPal JavaScript SDK", "title": "Pay $1,882.38", "sub": "The server sets the amount"},
        {"id": "s8", "popup": True, "a": 0, "b": min(m["popup_end"], m["popup_submit"] + 60), "voice": 8,
         "clicks": [m["popup_submit"]], "label": "PayPal sandbox · Orders v2", "title": "Real PayPal sandbox checkout",
         "sub": "PayPal's published test card · last wait shortened"},
        {"id": "s9", "a": m["popup_open"], "b": m["history_from"], "voice": 9, "label": "Orders v2 + Invoicing v2",
         "title": "Captured. Invoice marked paid.", "sub": f"Capture {receipt['capture']}"},
        {"id": "s10", "a": m["history_from"], "b": m["end"], "voice": None, "label": "AG Grid · audit history",
         "title": "Every line, audited", "sub": "Payment state on every line"},
    ], v, pad


def mix(tmp: Path, cues: list, clicks: list, pops: list, total: float) -> Path:
    """Voice lines at their cue times over the music bed, ticks on real clicks, pops on captions; -16 LUFS."""
    inputs, chains, labels = ["-i", str(MUSIC)], [], []
    chains.append(f"[0:a]atrim=0:{total:.2f},volume=0.16,afade=t=in:d=0.6,afade=t=out:st={total - 2.5:.2f}:d=2.5[m]")
    labels.append("[m]")
    k = 1
    for path, at, vol in ([(VOICE / f"L{i}.mp3", t, 1.0) for i, t in cues] + [(TICK, t, 0.6) for t in clicks]
                          + [(POP, t, 0.25) for t in pops]):
        inputs += ["-i", str(path)]
        ms = int(at * 1000)
        chains.append(f"[{k}:a]volume={vol},adelay={ms}|{ms}[a{k}]")
        labels.append(f"[a{k}]")
        k += 1
    chains.append(f"{''.join(labels)}amix=inputs={len(labels)}:normalize=0,atrim=0:{total:.2f},"
                  "loudnorm=I=-16:TP=-1.5:LRA=11[out]")
    out = tmp / "mix.wav"
    run([*inputs, "-filter_complex", ";".join(chains), "-map", "[out]", "-ar", "48000", "-ac", "2", str(out)])
    return out


def main() -> None:
    data = json.loads((FRAMES / "marks.json").read_text())
    m, receipt = data["marks"], data["receipt"]
    plan, voice_len, pad = scenes(m, receipt)
    with tempfile.TemporaryDirectory() as d:
        tmp, parts, cues, clicks, pops, t = Path(d), [], [], [], [], 0.0
        for sc in plan:
            footage = (sc["b"] - sc["a"]) / FPS
            need = voice_len[sc["voice"]] + pad if sc["voice"] else 0
            sc["length"] = round(need if sc.get("fit") else max(footage, need), 2)
            parts.append(popup_scene(tmp, sc) if sc.get("popup") else main_scene(tmp, sc))
            if sc["voice"]:
                cues.append((sc["voice"], t + 0.25))
            if sc["id"] != "s1":
                pops.append(t)
            speed = max(1.0, footage / sc["length"]) if sc.get("fit") else 1.0
            clicks += [t + (c - sc["a"]) / FPS / speed for c in sc.get("clicks", [])]
            print(f"{sc['id']:>4}  {t:6.2f}s  +{sc['length']:5.2f}s  {sc['title']}")
            t += sc["length"]
        parts.append(end_card(tmp, receipt, 5.0))
        print(f" end  {t:6.2f}s  + 5.00s")
        t += 5.0
        video = tmp / "video.mp4"
        (tmp / "parts.txt").write_text("".join(f"file '{p}'\n" for p in parts))
        run(["-f", "concat", "-safe", "0", "-i", str(tmp / "parts.txt"), "-c", "copy", str(video)])
        audio = mix(tmp, cues, clicks, pops, t)
        run(["-i", str(video), "-i", str(audio), "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac",
             "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(OUT)])
    print(OUT, f"{t:.1f}s")


if __name__ == "__main__":
    main()
