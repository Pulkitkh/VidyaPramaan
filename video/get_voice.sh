#!/usr/bin/env bash
# Fetches the offline voice for tts.py --engine kokoro into .build/voice, from the npm registry:
#   kokoro-js@1.2.1        official Kokoro package (Apache-2.0): the 54 voice style files
#   kokoro-q8-shards@1.0.0 Kokoro-82M v1.0 8-bit ONNX model (Apache-2.0), split in 6 parts
# The joined model must match the published SHA-256, or nothing is installed.
# Python packages (any venv): pip install kokoro-onnx==0.6.1 onnxruntime==1.31.0 espeakng-loader==0.2.4 soundfile
set -euo pipefail
cd "$(dirname "$0")"
OUT=.build/voice
SHA=fbae9257e1e05ffc727e951ef9b9c98418e6d79f1c9b6b13bd59f5c9028a1478
mkdir -p "$OUT/dl" && cd "$OUT/dl"
npm pack kokoro-js@1.2.1 kokoro-q8-shards@1.0.0 --silent > /dev/null
mkdir -p kjs shards
tar xzf kokoro-js-1.2.1.tgz -C kjs
tar xzf kokoro-q8-shards-1.0.0.tgz -C shards
cat shards/package/kokoro-q8.part{0,1,2,3,4,5}.bin > ../kokoro-v1.0.q8.onnx.tmp
echo "$SHA  ../kokoro-v1.0.q8.onnx.tmp" | sha256sum -c --quiet
mv ../kokoro-v1.0.q8.onnx.tmp ../kokoro-v1.0.q8.onnx
${PYTHON:-python3} - <<'PY'
import glob, os
import numpy as np
v = {os.path.basename(f)[:-4]: np.fromfile(f, dtype=np.float32).reshape(-1, 1, 256) for f in glob.glob("kjs/package/voices/*.bin")}
np.savez("../voices.npz", **v)
print(f"{len(v)} voices; model verified")
PY
