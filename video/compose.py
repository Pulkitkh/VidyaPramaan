"""Assembles the recorded scenes, the voice-over and the captions into the final video.

Reads .build/timeline.json (record.mjs) and .build/audio (tts.py); writes:
  <out>.mp4  1920x1080, 30 fps, H.264 + AAC, captions burned in
  <out>.srt  the same captions as a separate file (for YouTube's caption track)
Usage: python compose.py --out ../../deliverables/VidyaPramaan_SIH26263_demo
"""
import argparse
import json
import re
import subprocess
import wave
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
BUILD = HERE / ".build"
RATE = 48000
CARD_SCENES = {"title", "problem", "mobile", "honest", "close"}
MAX_CHARS = 84          # per caption (two lines of about 42)


def chunks(text: str) -> list[str]:
    """Caption-sized pieces: sentences, split further at commas or colons when too long."""
    out = []
    for sent in re.split(r"(?<=[.!?])\s+", text.strip()):
        if len(sent) <= MAX_CHARS:
            out.append(sent)
            continue
        parts, cur = re.split(r"(?<=[,:;])\s+", sent), ""
        for p in parts:
            if cur and len(cur) + 1 + len(p) > MAX_CHARS:
                out.append(cur)
                cur = p
            else:
                cur = f"{cur} {p}".strip()
        if cur:
            out.append(cur)
    # still too long (no punctuation): split on words
    final = []
    for c in out:
        while len(c) > MAX_CHARS:
            cut = c.rfind(" ", 0, MAX_CHARS)
            final.append(c[:cut])
            c = c[cut + 1:]
        final.append(c)
    return final


def wrap2(s: str) -> str:
    """Break a caption into two balanced lines."""
    if len(s) <= 44:
        return s
    words, best, bi = s.split(), None, 0
    for i in range(1, len(words)):
        a, b = " ".join(words[:i]), " ".join(words[i:])
        score = max(len(a), len(b))
        if best is None or score < best:
            best, bi = score, i
    return " ".join(words[:bi]) + r"\N" + " ".join(words[bi:])


def ts_srt(t: float) -> str:
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def ts_ass(t: float) -> str:
    cs = int(round(t * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


ASS_HEAD = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Inter,46,&H00FFFFFF,&H00FFFFFF,&H28160B00,&H28160B00,0,0,0,0,100,100,0,0,3,14,0,2,160,160,46,1
Style: Chap,Inter,26,&H00FFFFFF,&H00FFFFFF,&H001A7BE0,&H001A7BE0,1,0,0,0,100,100,0.5,0,3,9,0,7,690,0,14,1
Style: Tag,Inter,20,&H00FFFFFF,&H00FFFFFF,&H50160B00,&H50160B00,0,0,0,0,100,100,0,0,3,6,0,3,0,22,16,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--fps", type=int, default=30)
    args = ap.parse_args()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    spec = {s["id"]: s for s in json.loads((HERE / "narration.json").read_text())["scenes"]}
    tl = json.loads((BUILD / "timeline.json").read_text())
    audio_meta = json.loads((BUILD / "audio" / "durations.json").read_text())
    frames = tl["frames"]
    times = np.array([f["t"] for f in frames])

    # ---- picture: an ffconcat list holding each frame for as long as it was on screen within each scene
    lines, t_global, placed = ["ffconcat version 1.0"], 0.0, []
    last_file = None
    for seg in tl["segments"]:
        s0, s1 = seg["start"], seg["end"]
        i0 = int(np.searchsorted(times, s0, side="right")) - 1
        idx = [max(i0, 0)] + [i for i in range(max(i0 + 1, 0), len(frames)) if s0 < times[i] < s1]
        for k, i in enumerate(idx):
            a = s0 if k == 0 else times[i]
            b = s1 if k == len(idx) - 1 else times[idx[k + 1]]
            if b - a <= 0:
                continue
            lines += [f"file '{(BUILD / 'frames' / frames[i]['file']).as_posix()}'", f"duration {b - a:.4f}"]
            last_file = frames[i]["file"]
        placed.append({**seg, "at": t_global, "len": s1 - s0})
        t_global += s1 - s0
    lines.append(f"file '{(BUILD / 'frames' / last_file).as_posix()}'")  # concat demuxer needs the last file repeated
    (BUILD / "frames.ffconcat").write_text("\n".join(lines) + "\n")
    total = t_global

    # ---- sound: each scene's voice placed at its scene start plus the lead
    track = np.zeros(int((total + 1) * RATE), dtype=np.float32)
    have_audio = audio_meta["engine"] != "none"
    if have_audio:
        for p in placed:
            with wave.open(str(BUILD / "audio" / f"{p['id']}.wav")) as w:
                assert w.getframerate() == RATE and w.getnchannels() == 1
                x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
            o = int((p["at"] + p["lead"]) * RATE)
            track[o:o + len(x)] += x[: len(track) - o]
    with wave.open(str(BUILD / "voice.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes((np.clip(track, -1, 1) * 32767).astype(np.int16).tobytes())

    # ---- captions: pieces timed in proportion to their length within the scene's voice
    srt, ass, n = [], [ASS_HEAD], 0
    for p in placed:
        sc = spec[p["id"]]
        pieces = chunks(sc["text"])
        weights = np.array([len(c) + 6 for c in pieces], dtype=float)
        edges = np.concatenate([[0], np.cumsum(weights) / weights.sum()]) * p["audio"]
        for j, (c, a, b) in enumerate(zip(pieces, edges[:-1], edges[1:])):
            # back-to-back within a scene; the last caption lingers briefly after the voice ends
            t0, t1 = p["at"] + p["lead"] + a, p["at"] + p["lead"] + b + (0.6 if j == len(pieces) - 1 else -0.02)
            n += 1
            srt.append(f"{n}\n{ts_srt(t0)} --> {ts_srt(t1)}\n{c}\n")
            ass.append(f"Dialogue: 0,{ts_ass(t0)},{ts_ass(t1)},Cap,,0,0,0,,{wrap2(c)}")
        if p["id"] not in CARD_SCENES:
            if sc.get("chapter"):
                ass.append(f"Dialogue: 1,{ts_ass(p['at'])},{ts_ass(p['at'] + p['len'])},Chap,,0,0,0,,{sc['chapter']}")
            ass.append(f"Dialogue: 1,{ts_ass(p['at'])},{ts_ass(p['at'] + p['len'])},Tag,,0,0,0,,Synthetic demo data")
    out.with_suffix(".srt").write_text("\n".join(srt), encoding="utf-8")
    (BUILD / "captions.ass").write_text("\n".join(ass) + "\n", encoding="utf-8")

    # ---- encode
    vf = (f"scale=1920:1080:flags=lanczos,fps={args.fps},format=yuv420p,"
          f"subtitles={(BUILD / 'captions.ass').as_posix()}:fontsdir=/usr/share/fonts/opentype/inter")
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(BUILD / "frames.ffconcat"),
           "-i", str(BUILD / "voice.wav"), "-vf", vf, "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-tune", "stillimage",
           "-c:a", "aac", "-b:a", "160k", "-ar", str(RATE), "-movflags", "+faststart", "-t", f"{total:.3f}", str(out.with_suffix(".mp4"))]
    subprocess.run(cmd, check=True)
    (BUILD / "chapters.txt").write_text("\n".join(
        f"{int(p['at'] // 60)}:{int(p['at'] % 60):02d} {spec[p['id']].get('chapter') or ('Introduction' if p['id'] == 'title' else 'Close')}"
        for p in placed) + "\n")
    print(f"{out.with_suffix('.mp4')}  {total:.1f} s, {n} captions, voice: {audio_meta['engine']}")


if __name__ == "__main__":
    main()
