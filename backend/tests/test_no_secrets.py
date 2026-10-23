"""Fails if a credential or secret-looking value is committed to the repository."""
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

PATTERNS = {
    "private key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "AWS access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "GitHub token": re.compile(r"\b(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36}\b|\bgithub_pat_[A-Za-z0-9_]{50,}\b"),
    "Slack token": re.compile(r"\bxox[abpors]-[A-Za-z0-9-]{10,}"),
    "Google API key": re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    "Stripe live key": re.compile(r"\b[sr]k_live_[0-9A-Za-z]{16,}"),
    "Render API key": re.compile(r"\brnd_[A-Za-z0-9]{20,}"),
    "Hugging Face token": re.compile(r"\bhf_[A-Za-z0-9]{30,}"),
    "hard-coded secret": re.compile(
        r"""(?i)\b(secret|password|passwd|api[_-]?key|token)\b\s*[:=]\s*["'][A-Za-z0-9_\-+/=]{16,}["']"""),
    "credentials in URL": re.compile(r"[a-z+]+://[^\s:/<>]+:[^\s@<>]{6,}@[^\s]+"),
}
FORBIDDEN_FILES = re.compile(r"(^|/)(\.env(\..*)?|id_rsa.*|.*\.(pem|key|p12|pfx|sqlite|db))$")


def tracked_files() -> list[str]:
    try:
        out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    except (FileNotFoundError, subprocess.CalledProcessError):
        pytest.skip("not a git checkout")
    return [f for f in out.splitlines() if f]


def test_no_secret_files_are_tracked():
    bad = [f for f in tracked_files() if FORBIDDEN_FILES.search(f)]
    assert not bad, f"secret-type files are tracked: {bad}"


def test_no_secret_values_in_tracked_files():
    hits = []
    for f in tracked_files():
        path = ROOT / f
        if not path.is_file() or path.stat().st_size > 2_000_000:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue  # binary (images, decks)
        for name, rx in PATTERNS.items():
            for m in rx.finditer(text):
                if f.endswith("test_no_secrets.py"):
                    continue
                hits.append(f"{f}: {name}: {m.group(0)[:12]}…")
    assert not hits, "possible secrets committed:\n" + "\n".join(hits)
