# Demo video

Regenerates the narrated, captioned prototype walkthrough (1920×1080, about 5 minutes) from the running app.

| File | Role |
|---|---|
| `narration.json` | Script: one entry per scene, with caption text and an optional spoken form (`say`) |
| `tts.py` | Voice-over per scene; each scene lasts as long as its narration |
| `get_voice.sh` | Fetches the offline Kokoro-82M voice from npm and checks the model's SHA-256 |
| `record.mjs` | Drives the app scene by scene (cursor, highlights) and captures frames with Chromium's screencast |
| `cards.mjs` | Title, problem, phone, "what is real" and closing cards |
| `compose.py` | Joins frames, voice and captions into the MP4, plus an `.srt` caption file |

```bash
pip install kokoro-onnx==0.6.1 onnxruntime==1.31.0 espeakng-loader==0.2.4 soundfile   # any venv
./get_voice.sh                                    # once
python tts.py --engine kokoro                     # or --engine none for a silent timing preview
# fresh demo data, issuer shown as the public host
cd ../backend && VP_PUBLIC_BASE_URL=https://vidya-pramaan-sih26263.onrender.com python -m app.seed \
  && VP_PUBLIC_BASE_URL=https://vidya-pramaan-sih26263.onrender.com VP_DEMO_MODE=1 uvicorn app.main:app --port 8000 &
cd ../video && npm install && node record.mjs
python compose.py --out ../../deliverables/VidyaPramaan_SIH26263_demo
```

Every claim in the narration matches the app as recorded and `docs/CLAIMS.md`. If the app's wording or
data changes, check the highlight labels in `record.mjs` and the narration before re-recording.
