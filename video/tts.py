"""Voice-over for each scene in narration.json, plus its duration.

Engines (--engine):
  kokoro  Offline neural voice, Kokoro-82M (Apache-2.0). Run get_voice.sh once to fetch and verify the model.
          Default voice af_heart.
  edge    Microsoft neural voice via the edge-tts package (needs speech.platform.bing.com). Default voice:
          en-IN-PrabhatNeural (Indian English).
  piper   Offline neural voice (needs a Piper .onnx model, --model PATH).
  espeak  Offline, robotic; for checking timing only.
  none    No audio: durations estimated at 150 words a minute, for a silent captioned preview.

Usage: python tts.py --engine edge --out .build/audio
Writes <out>/<scene>.wav and <out>/durations.json.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RATE = 48000
VOICE_DIR = HERE / ".build" / "voice"
# Spoken forms for words an English voice would otherwise mispronounce. Captions keep the written form.
SAY = [(r"\bAICTE\b", "A-I-C-T-E"), (r"\bERP\b", "E-R-P"), (r"\bOTP\b", "O-T-P"), (r"\bPramaan\b", "Pra-maan"),
       (r"\blakh\b", "laakh"), (r"\bB\.Tech\b", "B Tech")]
_KOKORO = None


def spoken(text: str) -> str:
    for pat, rep in SAY:
        text = re.sub(pat, rep, text)
    return text


def run(cmd, **kw):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, **kw)


def to_wav(src: Path, dst: Path):
    # Mono 48 kHz, loudness-normalised so every scene sits at the same level.
    run(["ffmpeg", "-y", "-i", str(src), "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-ar", str(RATE), "-ac", "1", str(dst)])


def duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return float(out.strip())


def speak(engine: str, text: str, wav: Path, voice: dict, args):
    tmp = wav.with_suffix(".raw.wav") if engine != "edge" else wav.with_suffix(".mp3")
    if engine == "kokoro":
        global _KOKORO
        import soundfile as sf
        from kokoro_onnx import Kokoro
        if _KOKORO is None:
            _KOKORO = Kokoro(str(VOICE_DIR / "kokoro-v1.0.q8.onnx"), str(VOICE_DIR / "voices.npz"))
        samples, sr = _KOKORO.create(text, voice=args.voice, speed=args.speed, lang="en-us" if args.voice[0] == "a" else "en-gb")
        sf.write(str(tmp), samples, sr)
    elif engine == "edge":
        cmd = [args.edge_bin, "--voice", voice.get("edge", "en-IN-PrabhatNeural"), f"--rate={voice.get('rate', '+0%')}",
               "--text", text, "--write-media", str(tmp)]
        if os.getenv("HTTPS_PROXY"):
            cmd[1:1] = ["--proxy", os.environ["HTTPS_PROXY"]]
        run(cmd)
    elif engine == "piper":
        subprocess.run([args.piper_bin, "--model", args.model, "--output_file", str(tmp)], input=text.encode(),
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    elif engine == "espeak":
        run(["espeak-ng", "-v", "en-gb", "-s", "150", "-w", str(tmp), text])
    to_wav(tmp, wav)
    tmp.unlink(missing_ok=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", choices=["kokoro", "edge", "piper", "espeak", "none"], default="kokoro")
    ap.add_argument("--voice", default="af_heart", help="Kokoro voice")
    ap.add_argument("--speed", type=float, default=0.97, help="Kokoro speaking rate")
    ap.add_argument("--out", default=str(HERE / ".build" / "audio"))
    ap.add_argument("--model", help="Piper voice model (.onnx)")
    ap.add_argument("--edge-bin", default=shutil.which("edge-tts") or "edge-tts")
    ap.add_argument("--piper-bin", default=shutil.which("piper") or "piper")
    args = ap.parse_args()
    spec = json.loads((HERE / "narration.json").read_text())
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    durations = {}
    for sc in spec["scenes"]:
        wav = out / f"{sc['id']}.wav"
        if args.engine == "none":
            durations[sc["id"]] = round(len(sc.get("say", sc["text"]).split()) / 150 * 60, 2)
            continue
        speak(args.engine, spoken(sc.get("say", sc["text"])), wav, spec.get("voice", {}), args)
        durations[sc["id"]] = round(duration(wav), 2)
        print(f"{sc['id']:16s} {durations[sc['id']]:6.2f} s", file=sys.stderr)
    (out / "durations.json").write_text(json.dumps({"engine": args.engine, "durations": durations}, indent=1))
    print(f"total narration {sum(durations.values()):.1f} s", file=sys.stderr)


if __name__ == "__main__":
    main()
