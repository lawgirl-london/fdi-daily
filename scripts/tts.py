"""Turn out/episode.json's script into out/episode.mp3.

First choice is Microsoft Edge TTS (config "voice"). That service is unofficial and
Microsoft sometimes changes it without warning (e.g. the October 2026 403 errors), so
if it fails we fall back to Piper, a neural TTS that runs locally on the runner
(config "fallback_voice"), and the episode still goes out.
"""
import asyncio
import json
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

CONFIG = json.load(open("config.json"))
OUT = Path("out/episode.mp3")
PIPER_DIR = Path("out/piper")


def prepare(text: str) -> str:
    # Longest keys first so e.g. "NSI Act" wins over "NSI".
    for word in sorted(CONFIG["pronunciations"], key=len, reverse=True):
        text = re.sub(rf"\b{re.escape(word)}\b", CONFIG["pronunciations"][word], text)
    return text


def edge(text: str) -> None:
    import edge_tts

    async def run() -> None:
        await edge_tts.Communicate(text, CONFIG["voice"], rate=CONFIG["rate"]).save(str(OUT))

    for attempt in range(1, 4):
        try:
            asyncio.run(run())
            if OUT.exists() and OUT.stat().st_size > 10_000:
                return
            raise RuntimeError("Edge TTS produced an empty or tiny file")
        except Exception as e:  # network hiccups or service changes on Microsoft's side
            print(f"Edge TTS attempt {attempt} failed: {e}")
            if attempt < 3:
                time.sleep(10 * attempt)
    raise RuntimeError("Edge TTS failed after 3 attempts")


def piper(text: str) -> None:
    # Voice names look like en_GB-alan-medium -> en/en_GB/alan/medium/...
    voice = CONFIG.get("fallback_voice", "en_GB-alan-medium")
    lang, name, quality = voice.split("-")
    base = (
        "https://huggingface.co/rhasspy/piper-voices/resolve/main/"
        f"{lang.split('_')[0]}/{lang}/{name}/{quality}/{voice}"
    )
    PIPER_DIR.mkdir(parents=True, exist_ok=True)
    model = PIPER_DIR / f"{voice}.onnx"
    for suffix in (".onnx", ".onnx.json"):
        dest = PIPER_DIR / f"{voice}{suffix}"
        if not dest.exists():
            print(f"Downloading {dest.name}")
            urllib.request.urlretrieve(base + suffix, dest)

    wav = PIPER_DIR / "episode.wav"
    # One paragraph per line; Piper adds a natural pause between lines.
    lines = "\n".join(p.strip() for p in text.split("\n") if p.strip())
    subprocess.run(
        [sys.executable, "-m", "piper", "-m", str(model), "-f", str(wav)],
        input=lines, text=True, check=True,
    )
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav),
         "-codec:a", "libmp3lame", "-b:a", "64k", "-ac", "1", str(OUT)],
        check=True,
    )


def main() -> None:
    episode = json.load(open("out/episode.json"))
    script = episode["script"].strip()
    words = len(script.split())
    print(f"Script: {words} words (cap {CONFIG['max_words']})")
    if words > CONFIG["max_words"] * 1.15:
        sys.exit(f"Script too long: {words} words")

    text = prepare(script)
    try:
        edge(text)
        print(f"Audio made with Edge TTS ({CONFIG['voice']})")
        return
    except Exception as e:
        print(f"::warning::Edge TTS unavailable ({e}); falling back to Piper")

    try:
        piper(text)
    except Exception as e:
        sys.exit(f"Fallback TTS (Piper) also failed: {e}")
    print(f"Audio made with Piper ({CONFIG.get('fallback_voice', 'en_GB-alan-medium')})")


if __name__ == "__main__":
    main()
